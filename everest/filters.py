"""Optional structured filters; no place/event AND requirement by default."""
import datetime as dt
from email.utils import parsedate_to_datetime
import math


def timestamp(value):
    if value is None: return None
    try:
        if isinstance(value,(float,int)):
            return dt.datetime.fromtimestamp(value/1000 if value>100000000000 else value,dt.timezone.utc)
        try: parsed=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        except ValueError: parsed=parsedate_to_datetime(str(value))
        return parsed if parsed.tzinfo else None
    except (ValueError,TypeError,OverflowError): return None


def structured_match(item, options):
    """Apply only explicitly configured coordinate/numeric/time filters."""
    if not options: return True
    from .collect import select_path
    bbox=options.get('bbox')
    if bbox:
        try:
            lon,lat=select_path(item,options.get('coordinates_path','geometry.coordinates'))[:2]
            if not (bbox[0]<=lon<=bbox[2] and bbox[1]<=lat<=bbox[3]): return False
        except (KeyError,TypeError,IndexError): return False
    for path,bounds in options.get('numeric',{}).items():
        try: value=float(select_path(item,path))
        except (KeyError,TypeError,ValueError): return False
        if not math.isfinite(value): return False
        if bounds.get('min') is not None and value<bounds['min']: return False
        if bounds.get('max') is not None and value>bounds['max']: return False
    if options.get('after') or options.get('max_age_hours') is not None:
        try: value=timestamp(select_path(item,options['time_path']))
        except (KeyError,TypeError): return False
        if value is None: return False
        if options.get('after') and value<timestamp(options['after']): return False
        if options.get('max_age_hours') is not None and (dt.datetime.now(dt.timezone.utc)-value).total_seconds()>options['max_age_hours']*3600: return False
    return True
