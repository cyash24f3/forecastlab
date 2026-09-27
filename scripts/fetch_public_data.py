"""Download and adapt the CC BY 4.0 UCI Bike Sharing daily dataset.

No weather or same-day component counts are used as predictors: those would
not be known for the future rental days in this forecasting use case.
"""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
import pandas as pd

URL = 'https://archive.ics.uci.edu/static/public/275/bike%2Bsharing%2Bdataset.zip'
ROOT = Path(__file__).resolve().parents[1]


def main():
    request = urllib.request.Request(URL, headers={'User-Agent': 'ForecastLab educational dataset adapter'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(3 * 1024 * 1024)
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        source = pd.read_csv(archive.open('day.csv'))
    converted = pd.DataFrame({'date': source.dteday, 'series_id': 'Bike rentals', 'value': source.cnt})
    destination = ROOT / 'examples' / 'bike-rentals.csv'
    converted.to_csv(destination, index=False)
    metadata = {
        'title': 'Bike Sharing — daily rental counts',
        'citation': 'Fanaee-T, H. (2013). Bike Sharing [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5W894.',
        'source_url': 'https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset',
        'download_url': URL,
        'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'archive_sha256': hashlib.sha256(raw).hexdigest(),
        'transformation': 'day.csv: dteday renamed date; cnt renamed value; constant series_id Bike rentals; all other columns excluded.',
        'rows': len(converted), 'start': str(source.dteday.min()), 'end': str(source.dteday.max()),
        'limitation': 'Historical 2011–2012 rental counts. Forecasts beyond the last observation are a historical demonstration, not current rental demand.'
    }
    (ROOT / 'examples' / 'bike-rentals.source.json').write_text(json.dumps(metadata, indent=2))
    print(f'Saved {len(converted)} daily observations to {destination}')


if __name__ == '__main__':
    main()
