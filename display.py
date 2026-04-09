# kalshi_bot/display.py
"""
kalshi_bot/display.py — Terminal Dashboard
"""
import os
import time
from colorama import Fore, Back, Style, init
from tabulate import tabulate

init(autoreset=True)
LINE = "─" * 72


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def clr(text, color):
    return f"{color}{text}{Style.RESET_ALL}"


def pnl_str(val: float) -> str:
    if val > 0:
        return clr(f"+${val:.4f}", Fore.GREEN)
    elif val < 0:
        return clr(f"-${abs(val):.4f}", Fore.RED)
    return clr(f"${val:.4f}", Fore.WHITE)


def mom_str(val: float) -> str:
    arrow = "UP" if val > 0 else ("DN" if val < 0 else "--")
    color = Fore.GREEN if val > 0 else (Fore.RED if val < 0 else Fore.WHITE)
    return clr(f"{arrow} {val:+.4%}", color)


class Display:
    """Terminal UI for the Kalshi trading bot."""

    def render_opportunities(self, opportunities: list) -> None:
        if not opportunities:
            print(f"\n{clr('No opportunities found this cycle.', Style.DIM)}")
            return
        print(f"\n{clr('TOP OPPORTUNITIES', Fore.MAGENTA + Style.BRIGHT)}")
        print(clr(LINE, Fore.MAGENTA))
        rows = []
        for opp in opportunities[:8]:
            ticker   = clr(opp.ticker, Fore.CYAN + Style.BRIGHT)
            yes_p    = opp.yes_price
            vol      = opp.volume_24h
            question = opp.question[:38] + "..." if len(opp.question) > 38 else opp.question
            uncert   = 1.0 - abs(yes_p - 0.5) * 2
            bar_len  = int(uncert * 8)
            bar      = ("#" * bar_len).ljust(8)
            bar_col  = Fore.GREEN if uncert > 0.7 else (Fore.YELLOW if uncert > 0.4 else Fore.RED)
            rows.append([
                ticker,
                opp.category,
                f"{yes_p:.3f}",
                clr(bar, bar_col),
                f"${vol:,.0f}",
                question,
            ])
        print(tabulate(rows,
            headers=["Ticker", "Category", "YES", "Uncert", "Vol 24h", "Market"],
            tablefmt="simple"))

    def render_positions(self, risk) -> None:
        print(f"\n{clr('ACTIVE POSITIONS', Fore.CYAN + Style.BRIGHT)}")
        print(clr(LINE, Fore.CYAN))
        if not risk.positions:
            print(clr("  No open positions.", Style.DIM))
            return
        rows = []
        for ticker, pos in risk.positions.items():
            rows.append([
                clr(pos.ticker, Fore.CYAN),
                pos.side,
                f"{pos.contracts} contracts",
                f"{pos.entry_price:.3f}",
            ])
        print(tabulate(rows, headers=["Ticker", "Side", "Contracts", "Entry"], tablefmt="simple"))

    def render_risk_panel(self, risk) -> None:
        halted, reason = risk.is_halted()
        status = clr(f"HALTED: {reason}", Fore.RED + Style.BRIGHT) if halted \
                 else clr("RUNNING", Fore.GREEN + Style.BRIGHT)
        print(f"\n{clr('RISK & PERFORMANCE', Fore.YELLOW + Style.BRIGHT)}")
        print(clr(LINE, Fore.YELLOW))
        print(f"  Status    : {status}")
        print(f"  Daily PnL : {pnl_str(risk._daily_pnl)}")
        print(f"  Exposure  : ${risk.total_exposure():.2f}  |  "
              f"Positions: {len(risk.positions)}")

    def render_signals(self, signals: list) -> None:
        if not signals:
            return
        print(f"\n{clr('LAST SIGNALS', Fore.WHITE + Style.BRIGHT)}")
        print(clr(LINE, Fore.WHITE))
        for sig in signals[:5]:
            icon = clr("[Y]", Fore.GREEN) if getattr(sig, "edge_pct", 0) >= 0.05 else clr("[?]", Fore.YELLOW)
            print(f"  {icon}  {sig.ticker:<22}  {sig.side:<5}  "
                  f"edge={sig.edge_pct:.1%}  contracts={sig.contracts}")

    def render_status(self, opportunities: list, signals: list, risk) -> None:
        """Full status render: header + opportunities + positions + risk."""
        clear()
        print(f"\n{clr('KALSHI QUANT BOT', Fore.CYAN + Style.BRIGHT)}  "
              f"{clr(time.strftime('%H:%M:%S'), Style.DIM)}")
        print(clr(LINE, Fore.CYAN))
        self.render_opportunities(opportunities)
        self.render_positions(risk)
        self.render_risk_panel(risk)
        if signals:
            self.render_signals(signals)
        print(f"\n{clr(LINE, Fore.CYAN)}")
        print(clr("  Ctrl+C to stop\n", Style.DIM))
