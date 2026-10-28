# Wymagania projektu i jak je spełniamy

Wyższy próg obejmuje niższe. Projekt jest robiony od razu pod ocenę 5,0. Minimum danych po wypakowaniu: 5 GB. Trzymamy 5,5 GB, żeby pomiar `du` nie wyszedł na styk.

## Ocena 3,0

| Wymaganie | Realizacja |
|---|---|
| Problem i udokumentowane źródło | Lichess Open Database, CC0, opis w `DANE-I-ANALIZY.md` |
| Import do lokalnego MongoDB | Metadane importu i ranking FIDE. Surowych partii do Mongo nie wkładamy |
| Sprawdzenie, czyszczenie i co najmniej trzy analizy | Reguły odrzuceń oraz trzy joby |
| Wizualizacja albo czytelne zestawienie | Trzy wykresy PNG i tabele w sprawozdaniu |
| Kod, dane albo instrukcja pobrania, sprawozdanie na platformie Delta | Skrypt pobierania, README, sprawozdanie. Bez pliku PGN |

Prezentacja na samą trójkę nie jest wymagana. Przy piątce jest.

## Ocena 4,0

| Wymaganie | Realizacja |
|---|---|
| Dwie bazy: własna oraz darmowa chmura | MongoDB lokalnie oraz Atlas M0 |
| Ponowny import bez niekontrolowanego powielania | Nadpisanie pliku w HDFS, upsert po kluczu, skrypt sprawdzający `count` |
| Dane do co najmniej jednej bazy ze web scrapingu | Listy Top HTML z ratings.fide.com do lokalnego Mongo |
| Prezentacja przepływu i wyników | Konspekt w etapie 9: HDFS, trzy joby, drugi import |

## Ocena 5,0

| Wymaganie | Realizacja |
|---|---|
| Główny zbiór w HDFS | `/user/chess/raw/lichess_2026-09.pgn` |
| Hadoop MapReduce przetwarza dane i liczy statystykę | Hadoop Streaming, Python. Trzy mappery, jeden reducer sumujący |
| W Mongo wyniki, agregaty albo metadane | Kolekcja `aggregates` w Atlasie, `import_runs` lokalnie |
| Szyfrowane połączenie i uwierzytelnienie | Lokalnie TLS oraz SCRAM. Atlas przez `mongodb+srv` |
| Wizualizacja albo MongoDB Compass | Wykresy oraz zrzut kolekcji w Compass albo w Atlasie |
| Obszerne sprawozdanie po polsku | Problem i dane, implementacja, uruchomienie i możliwości |
| Prezentacja działania, Hadoopa i wyników | Ten sam materiał co sprawozdanie, krótko, na żywo drugi import |

Dane w HDFS mogą pochodzić z otwartego zbioru. Scraping nie musi zasilać HDFS. Tak jest zrobione: PGN jest z Lichess, scraping zasila tylko lokalną bazę.

## Czego treść zajęć nie wymaga

Nie wymaga silnika szachowego, karty graficznej, Sparka ani tego, żeby każda analiza używała każdego bajtu. Wymaga, żeby to MapReduce wykonał analizę statystyczną. Skrypt ze Stockfishem puszczony obok klastra tego punktu nie spełnia.

## Dowody do sprawozdania

- `hdfs dfs -du -h` z wynikiem co najmniej 5,5 GB
- logi trzech jobów i liczniki odrzuconych partii
- `count` agregatów i rankingu FIDE przed drugim importem i po nim, bez wzrostu
- połączenie klienckie z TLS (lokalnie z plikiem CA, Atlas przez SRV)
- trzy wykresy
