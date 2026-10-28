# Prompty do wklejenia

Każdy prompt w nowej wiadomości, po zakończeniu poprzedniego etapu. Agent ma w repozytorium pliki `AGENTS.md` i `docs/`.

## Etap 0. Pierwsza wiadomość w świeżym repozytorium

```text
Przeczytaj po kolei AGENTS.md, docs/WYMAGANIA.md, docs/DANE-I-ANALIZY.md i docs/PLAN.md.

Zrób wyłącznie etap 0 z docs/PLAN.md. Zainstaluj skill python-testing w tym repozytorium, zakres Project, bez flagi -g. Jeśli instalator pyta o metodę na Windowsie, wybierz Copy.

Nie implementuj parsera, analiz, scrapera, pobierania dumpa ani jobów MapReduce. Nie ściągaj pliku Lichess.

Na końcu napisz, które pliki powstały, gdzie leży skill, czy Docker faktycznie wstał, i że następny krok to etap 1 z docs/PROMPTY.md.
```

## Etap 1

```text
Zrób wyłącznie etap 1 z docs/PLAN.md. Trzymaj się definicji z docs/DANE-I-ANALIZY.md.
Najpierw fixtury i testy, potem parser. Nie stawiaj na nowo Dockera i nie ściągaj dumpa.
```

## Etap 2

```text
Zrób wyłącznie etap 2 z docs/PLAN.md. Doprowadź Docker, HDFS i lokalne Mongo z TLS do warunku ukończenia. Hasła tylko przez środowisko, nie w gicie.
```

## Etap 3

```text
Zrób wyłącznie etap 3 z docs/PLAN.md. Pobierz tylko próbkę 50 MB nieskompresowanego PGN. Trybu --full nie uruchamiaj.
```

## Etap 4

```text
Zrób wyłącznie etap 4 z docs/PLAN.md. Scraper ma brać adresy list z ratings.fide.com. Pokaż count przed drugim przebiegiem i po nim.
```

## Etap 5

```text
Zrób wyłącznie etap 5 z docs/PLAN.md. Job na próbce ma zwrócić te same sumy co parser lokalnie. Stockfisha nie uruchamiaj.
```

## Etap 6

```text
Zrób wyłącznie etap 6 z docs/PLAN.md. Agregaty do Atlasu, metadane importu lokalnie. Jeśli w .env nie ma ATLAS_URI, zatrzymaj się i napisz, czego brakuje. Nie zapisuj agregatów w zastępczej bazie.
```

## Etap 7

```text
Zrób wyłącznie etap 7 z docs/PLAN.md. Trzy wykresy z wyników próbki. Bullet osobno od klasyka.
```

## Etap 8

```text
Zrób wyłącznie etap 8 z docs/PLAN.md. Uruchom tryb pełny, próg 5,5 GB, potem te same trzy joby. Zachowaj du i logi w sprawozdanie/dowody. Nie commituj pliku PGN.
```

## Etap 9

```text
Zrób wyłącznie etap 9 z docs/PLAN.md. Sprawozdanie po polsku. Osobno napisz, że dokładność dotyczy około 6% partii z gotowym [%eval], a listy FIDE nie są tymi samymi graczami co nicki Lichess.
```
