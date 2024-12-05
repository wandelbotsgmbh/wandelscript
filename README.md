# Wandelscript

## Introduction


## Grammar

The Wandelscript grammar is defined under `/wandelscript/grammar`.

To generate the parser, run the following command:

```bash
cd wandelscript/grammar && poetry run antlr4 -Dlanguage=Python3 -visitor *.g4
```
