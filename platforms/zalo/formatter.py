import re


def strip_markdown(text: str) -> str:
    """Convert Telegram markdown to plain text for Zalo."""
    # Remove bold: *text* -> text
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # Remove italic: _text_ -> text
    text = re.sub(r'_([^_]+)_', r'\1', text)
    # Remove code blocks: ```text``` -> text
    text = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).strip('`').strip(), text)
    # Remove inline code: `text` -> text
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove link syntax: [text](url) -> text (url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    return text
