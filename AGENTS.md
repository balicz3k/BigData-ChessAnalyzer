# Instrukcje dla agenta

Przeczytaj ten plik, potem `docs/WYMAGANIA.md`, `docs/DANE-I-ANALIZY.md` i `docs/PLAN.md`. Przy implementacji etapu trzymaj się definicji z `docs/DANE-I-ANALIZY.md`. Nie wymyślaj innego tematu, innego miesiąca ani innych analiz.

## Co to jest

Repozytorium `partie-lichess`. Tytuł projektu: **Tempo, zegar i dokładność partii szachowych na podstawie bazy Lichess**.

Jednostką liczenia jest półruch: jego zapis oraz komentarze `[%clk]` i, gdy są, `[%eval]`. Nagłówek daje tempo, ranking i wynik. Silnika szachowego nie uruchamiamy. Oficjalny Stockfish nie używa karty graficznej, a przeliczenie całego wycinka na CPU nie mieści się w czasie projektu.

## Który etap wolno ruszyć

Rób tylko etap nazwany w wiadomości użytkownika. Gdy wiadomość nie podaje etapu, nie zaczynaj następnego. Etap jest skończony, gdy spełniony jest warunek z `docs/PLAN.md`, nie gdy pliki zostały utworzone.

Po zakończeniu etapu napisz: co powstało, jak to sprawdzono i który prompt z `docs/PROMPTY.md` jest następny. Nie przechodź do kolejnego etapu w tej samej turze.

## Decyzje, których nie wolno zmieniać

- Miesiąc danych: wrzesień 2026. Adres pliku jest w `docs/DANE-I-ANALIZY.md`.
- W HDFS leży surowy PGN, ścieżka `/user/chess/raw/lichess_2026-09.pgn`, próg 5,5 GB (5 500 000 000 bajtów) po rozpakowaniu.
- Trzy joby MapReduce: `ply_by_tc_elo`, `time_trouble_by_tc`, `accuracy_by_elo`. Definicje metryk są w `docs/DANE-I-ANALIZY.md`.
- Dokładność liczymy z gotowych `[%eval]`. Do mappera nie wolno podpinać Stockfisha ani Leeli.
- Lokalne MongoDB trzyma ranking FIDE i metadane importu. Atlas trzyma agregaty trzech jobów.
- Zapis jest idempotentny: ten sam plik w HDFS jest nadpisywany, Mongo używa upsertu po kluczu unikalnym. Drugi przebieg nie zwiększa liczby dokumentów.
- Hasła, URI i certyfikaty prywatne nie wchodzą do gita. W repozytorium jest tylko `.env.example`.
- Nie łączymy nazwisk FIDE z nickami Lichess.
- Na Deltę nie wgrywamy gigabajtów. W repozytorium nie commitujemy PGN, `.zst` ani katalogu `data/` poza `.gitkeep`.

## Styl pracy

- Python 3.11. Zależności w `requirements.txt`.
- Najpierw test, potem kod, tam gdzie etap dotyczy parsera albo wzorów.
- Wspólna funkcja parsująca PGN jest importowana przez testy i przez mappery. Logiki zegara i dokładności nie kopiujemy w trzech miejscach.
- Mapper Hadoop emituje jeden rekord agregatu na partię (albo na stronę), reducer tylko sumuje liczby całkowite.
- Komunikaty błędów mają mówić, który próg nie został spełniony (rozmiar pliku, brak `[%clk]`, drugi import zwiększył `count`).

## Czego nie robić przy okazji

Nie dodawaj czwartej analizy, aplikacji webowej, Sparka, modelu uczenia maszynowego, odtwarzania szachownicy ani pobierania całego miesiąca (około 29 GB spakowane, po rozpakowaniu ponad 200 GB). Roszady, bicia i szachy z zapisu SAN wolno doliczyć później tylko wtedy, gdy użytkownik o to poprosi.
