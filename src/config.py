"""
Configuration management for Lien Automation
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def load_sites_config(config_path: str = None) -> Dict[str, Any]:
    """Load sites configuration from sites.json"""
    if config_path is None:
        # Try multiple locations
        possible_paths = [
            Path('config/sites.json'),
            Path('sites.json'),
            Path(__file__).parent.parent / 'config' / 'sites.json',
            Path(__file__).parent.parent / 'sites.json',
        ]
    else:
        possible_paths = [Path(config_path)]

    for path in possible_paths:
        if path.exists():
            logger.info("Loading sites config from %s", path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Support both formats: direct list or {"sites": [...]}
                if isinstance(data, list):
                    return {'sites': data}
                return data

    logger.warning("sites.json not found, using default config")
    return {'sites': []}


def get_site_by_id(site_id: int, config: Dict = None) -> Optional[Dict[str, Any]]:
    """Get site configuration by ID"""
    if config is None:
        config = load_sites_config()

    sites = config.get('sites', [])
    for site in sites:
        if site.get('id') == site_id:
            return site
    return None


def get_enabled_sites(config: Dict = None) -> List[Dict[str, Any]]:
    """Get all enabled sites"""
    if config is None:
        config = load_sites_config()

    sites = config.get('sites', [])
    return [s for s in sites if s.get('enabled', True)]
