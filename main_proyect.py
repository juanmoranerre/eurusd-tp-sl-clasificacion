from pathlib import Path
import subprocess


# ============================================================
# CONFIGURACIÓN
# ============================================================

INSTRUMENT = "EURUSD"

START_YEAR = 2019
END_YEAR = 2026

AWS_REGION = "eu-west-1"
S3_BUCKET = "s3://cfg-public-proper-wallaby"

DATA_DIR = Path("data/raw/m1")


# ============================================================
# DESCARGAR UN AÑO
# ============================================================

def download_year(year: int):

    source = f"{S3_BUCKET}/{INSTRUMENT}/{year}/"
    destination = DATA_DIR / str(year)

    destination.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 70)
    print(f"DESCARGANDO EURUSD M1 — {year}")
    print("=" * 70)
    print(f"Origen : {source}")
    print(f"Destino: {destination}")
    print()

    command = [
        "aws",
        "s3",
        "sync",
        source,
        str(destination),
        "--region",
        AWS_REGION,
        "--request-payer",
        "requester",

        # No descargar nada por defecto
        "--exclude",
        "*",

        # Solo velas M1 BID diarias
        "--include",
        "*BID_candles_min_1.bi5",
    ]

    result = subprocess.run(command)

    if result.returncode == 0:
        print()
        print(f"✓ Año {year} terminado correctamente.")
        return True

    print()
    print(f"✗ Error descargando {year}.")
    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("EUR/USD — DUKASCOPY S3 M1 DOWNLOADER")
    print("=" * 70)

    print(f"Instrumento : {INSTRUMENT}")
    print(f"Periodo     : {START_YEAR} → {END_YEAR}")
    print(f"Destino     : {DATA_DIR}")
    print("=" * 70)

    successful = 0
    failed = 0

    for year in range(START_YEAR, END_YEAR + 1):

        success = download_year(year)

        if success:
            successful += 1
        else:
            failed += 1

    print()
    print("=" * 70)
    print("DESCARGA FINALIZADA")
    print("=" * 70)

    print(f"Años correctos : {successful}")
    print(f"Años con error : {failed}")
    print("=" * 70)


if __name__ == "__main__":
    main()