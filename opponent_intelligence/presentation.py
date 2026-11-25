"""Shared charcoal/slate presentation tokens; no analytical calculations."""
from pathlib import Path
import streamlit as st

ACCENT = '#65b7b0'
TEXT = '#e2e8f0'
MUTED = '#a6b3c5'
BORDER = '#2a3747'
SURFACE = '#182230'


def styles():
    st.html('<style>' + (Path(__file__).parent / 'resources' / 'theme.css').read_text() + '</style>')
