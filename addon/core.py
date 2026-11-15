"""Portable configuration; no Anki or Qt dependency, no stored credentials."""
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def validate(config):
    value = dict(config)
    binary = Path(value.get('binary', '')).expanduser()
    if not binary.is_file():
        raise ValueError('请选择本机官方 tunnel-client 可执行文件。')
    value['binary'] = str(binary.resolve())
    if not re.fullmatch(r'tunnel_(?:[a-z0-9]{4}_)?[a-z0-9]{32}', value.get('tunnel_id', '')):
        raise ValueError('请填写已有的完整 Tunnel ID。')
    organization = value.get('organization_id', '').strip()
    if organization and not re.fullmatch(r'org-[A-Za-z0-9]+', organization):
        raise ValueError('Organization ID 格式无效。')
    value['organization_id'] = organization
    url = urlsplit(value.get('mcp_url', ''))
    try:
        local = ipaddress.ip_address(url.hostname).is_loopback
        port = url.port
    except (ValueError, TypeError):
        local, port = False, None
    if (url.scheme != 'http' or not local or not port or url.username or
            url.password or url.query or url.fragment):
        raise ValueError('MCP 地址须为无凭据的回环 HTTP 地址，例如 http://127.0.0.1:3141/。')
    return value


def profile(config, health_file):
    # JSON is valid YAML. Keys are supported by the official tunnel-client CLI.
    return {
        'config_version': 1,
        'control_plane': {
            'base_url': 'https://api.openai.com',
            'api_key': 'env:CONTROL_PLANE_API_KEY',
            'tunnel_id': config['tunnel_id'],
        },
        'mcp': {'server_urls': [{'channel': 'main', 'url': config['mcp_url']}]},
        'health': {'listen_addr': '127.0.0.1:0', 'url_file': str(health_file)},
        'log': {'file': 'stdout', 'format': 'json', 'level': 'info'},
    }


def redact(text, secret=''):
    if secret:
        text = text.replace(secret, '[REDACTED]')
    return re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED]', text)


def health_url(path):
    url = Path(path).read_text(encoding='utf-8').strip()
    parts = urlsplit(url)
    if (parts.scheme != 'http' or parts.hostname != '127.0.0.1' or
            not parts.port or parts.username or parts.password or parts.query or
            parts.fragment or parts.path not in ('', '/')):
        raise ValueError('客户端健康地址不是预期回环地址。')
    return url.rstrip('/')


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    path.chmod(0o600)
