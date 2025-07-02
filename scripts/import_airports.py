import os
import sys
import pandas as pd
from sqlalchemy import create_engine

sys.path.append(os.path.dirname(__file__) + '/..')
from data_manager import Base, Airport
from config import config


def main():
    db = config.DATABASE
    db_url = f"postgresql://{db.USER}:{db.PASSWORD}@{db.HOST}:{db.PORT}/{db.NAME}"
    try:
        engine = create_engine(db_url)
        engine.connect()
    except Exception:
        sqlite_path = 'data/flight_data.sqlite'
        engine = create_engine(f"sqlite:///{sqlite_path}")

    Base.metadata.create_all(engine)

    df = pd.read_csv('data/statics/airports.csv')
    columns = {
        'iata_code': 'iata',
        'icao_code': 'icao',
        'name': 'name',
        'municipality': 'city',
        'iso_country': 'country',
        'type': 'type'
    }
    df = df[list(columns.keys())]
    df.rename(columns=columns, inplace=True)
    df.to_sql('airports', engine, if_exists='replace', index=False)
    print(f"Imported {len(df)} airports")


if __name__ == '__main__':
    main()
