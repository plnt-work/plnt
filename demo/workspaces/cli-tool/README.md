# todo

A command-line todo list stored in a JSON file.

    python -m todo add "buy milk" --due 2026-10-03
    python -m todo list
    python -m todo done 1

Dates are ISO (YYYY-MM-DD). The file lives at `~/.todo.json` unless
`TODO_FILE` is set.
