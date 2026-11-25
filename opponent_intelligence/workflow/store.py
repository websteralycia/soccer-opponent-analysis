"""Report-isolated SQLite persistence; no shared global connection."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib,json,os,sqlite3,uuid
from pathlib import Path

CATEGORIES=('Defensive organization','Transitions','Buildup and progression','Attacking patterns','Set pieces','Match context','General')
STATUSES=('Draft','Needs Video Review','Confirmed')
CLASSIFICATIONS=('Potential Weakness','Opponent Strength','Tactical Tendency')
TEXT_FIELDS=('title','observation','supporting_evidence','contradictory_evidence','match_context','video_reference',
             'interpretation','coaching_implication','coach_summary','coach_observation','coach_consideration')


def report_identifier(result,fingerprint=None):
    if fingerprint and len(fingerprint)==64 and all(c in '0123456789abcdef' for c in fingerprint):
        return 'pdf:'+fingerprint
    digest=hashlib.sha256((result.team+'|'+str(result.matches)).encode())
    for name,frame in sorted(result.tables.items()):
        digest.update(name.encode());digest.update(frame.to_csv(index=False).encode('utf-8'))
    return 'dataset:'+digest.hexdigest()


def default_path():
    return Path(os.environ.get('SOCCER_INTELLIGENCE_DB',Path(__file__).resolve().parents[2]/'data'/'scouting.sqlite3'))


class FindingsStore:
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else default_path()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS findings(
                id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES reports(id),
                payload TEXT NOT NULL, included INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS findings_report ON findings(report_id,position,created);
            ''')

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()

    def register(self,report_id,metadata):
        with self.connection() as db:
            db.execute('INSERT INTO reports(id,metadata) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata',
                       (report_id,json.dumps(metadata,ensure_ascii=False)))

    @staticmethod
    def validated(payload):
        data={key:str('' if payload.get(key) is None else payload.get(key,'')).strip() for key in TEXT_FIELDS}
        if not data['title']:raise ValueError('A finding title is required.')
        if any(len(value)>20000 for value in data.values()):raise ValueError('Finding text exceeds 20,000 characters per field.')
        data['category']=payload.get('category','General');data['status']=payload.get('status','Draft')
        if data['category'] not in CATEGORIES or data['status'] not in STATUSES:raise ValueError('Unknown category or status.')
        classification=payload.get('classification')
        if classification=='':classification=None
        if classification is not None and classification not in CLASSIFICATIONS:
            raise ValueError('Unknown finding classification.')
        data['classification']=classification
        refs=payload.get('source_refs',[])
        if not isinstance(refs,list) or any(not isinstance(ref,dict) for ref in refs):raise ValueError('Evidence references must be structured records.')
        data['source_refs']=refs
        data['visual_key']=str(payload.get('visual_key',''))
        players=payload.get('highlight_players',[])
        if not isinstance(players,list) or any(not isinstance(name,str) for name in players) or len(players)>6:
            raise ValueError('Player highlights must be a list of up to six report player names.')
        data['highlight_players']=list(dict.fromkeys(players))
        return data

    @staticmethod
    def decode(row):
        if row is None:raise LookupError('Finding not found in this report.')
        data=json.loads(row['payload'])
        data.setdefault('classification',None)  # Legacy payloads are read without rewriting them.
        data.update(id=row['id'],report_id=row['report_id'],included=bool(row['included']),position=row['position'],
                    created=row['created'],updated=row['updated'])
        return data

    def list(self,report_id,category=None,status=None,classification='All'):
        with self.connection() as db:
            rows=db.execute('SELECT * FROM findings WHERE report_id=? ORDER BY position,created,id',(report_id,)).fetchall()
        findings=[self.decode(row) for row in rows]
        return [f for f in findings if (not category or f['category']==category) and (not status or f['status']==status)
                and (classification=='All' or f.get('classification')==classification)]

    def get(self,report_id,finding_id):
        with self.connection() as db:
            return self.decode(db.execute('SELECT * FROM findings WHERE id=? AND report_id=?',(finding_id,report_id)).fetchone())

    def create(self,report_id,payload):
        data=self.validated(payload);ident=uuid.uuid4().hex;now=datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            position=db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM findings WHERE report_id=?',(report_id,)).fetchone()[0]
            db.execute('INSERT INTO findings VALUES(?,?,?,?,?,?,?)',(ident,report_id,json.dumps(data,ensure_ascii=False),0,position,now,now))
        return self.get(report_id,ident)

    def update(self,report_id,finding_id,payload):
        existing=self.get(report_id,finding_id)
        data=self.validated(dict(existing,**payload))
        with self.connection() as db:
            cursor=db.execute('UPDATE findings SET payload=?,updated=? WHERE id=? AND report_id=?',
                (json.dumps(data,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),finding_id,report_id))
            if cursor.rowcount!=1:raise LookupError('Finding not found in this report.')
        return self.get(report_id,finding_id)

    def delete(self,report_id,finding_id):
        with self.connection() as db:
            cursor=db.execute('DELETE FROM findings WHERE id=? AND report_id=?',(finding_id,report_id))
            if cursor.rowcount!=1:raise LookupError('Finding not found in this report.')

    def select(self,report_id,ordered_ids):
        if len(set(ordered_ids))!=len(ordered_ids) or len(ordered_ids)>3:raise ValueError('Choose up to three unique findings.')
        with self.connection() as db:
            known={r[0] for r in db.execute('SELECT id FROM findings WHERE report_id=?',(report_id,))}
            if not set(ordered_ids).issubset(known):raise LookupError('Selection contains a finding from another report or a deleted finding.')
            db.execute('UPDATE findings SET included=0 WHERE report_id=?',(report_id,))
            for position,ident in enumerate(ordered_ids):
                db.execute('UPDATE findings SET included=1,position=? WHERE report_id=? AND id=?',(position,report_id,ident))

    def selected(self,report_id):
        return [f for f in self.list(report_id) if f['included']]
