#!/usr/bin/env bash
# Paczka na Deltę w do_oddania/: kod (zip z gita, bez danych i sekretów),
# sprawozdanie PDF, prezentacja PDF i instrukcja pobrania danych.
# Zip powstaje z ostatniego commitu, więc najpierw trzeba zacommitować zmiany.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=do_oddania
ZIP=$OUT/jakub_balicki_bigdata_projekt1_kod.zip
mkdir -p "$OUT"

git archive --format=zip --prefix=BigData-ChessAnalyzer/ -o "$ZIP" HEAD -- . ':(exclude)do_oddania'
cp sprawozdanie_latex/sprawozdanie.pdf "$OUT/jakub_balicki_bigdata_projekt1_sprawozdanie.pdf"
cp prezentacja/prezentacja.pdf "$OUT/jakub_balicki_bigdata_projekt1_prezentacja.pdf"

# kontrola: w zipie nie może być .env, kluczy, certyfikatów ani danych PGN (poza małymi fixturami testów)
if unzip -Z1 "$ZIP" | grep -E '(^|/)\.env$|\.pem$|\.key$|\.zst$|\.pgn$' | grep -v 'tests/fixtures/'; then
  echo "BŁĄD: w zipie są pliki, których nie wolno oddawać" >&2
  exit 1
fi
echo "Paczka gotowa:"
ls -lh "$OUT"
