"""Deprecated entrypoint.

Use streak_bot.py with an explicit action instead. This file intentionally
does not send messages, so running `python main.py` cannot trigger a send.
"""


def main():
    print("main.py is disabled. Use: python streak_bot.py --send")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
