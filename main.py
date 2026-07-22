import pyodbc
import random
import re
import unicodedata
import os

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

console = Console()

SERVER_NAME = r'localhost'
DATABASE_NAME = 'NBA_Project'
conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER_NAME};DATABASE={DATABASE_NAME};Trusted_Connection=yes;"


def clean_string(text):
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    ascii_text = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
    cleaned = re.sub(r"['`’\-]", "", ascii_text.lower())
    return " ".join(cleaned.split())


def format_val(val, is_float=False):
    if val is None or str(val).strip() == "":
        return "-"
    if is_float:
        try:
            return f"{float(val):.3f}"
        except (ValueError, TypeError):
            return "-"
    return str(val)


class SmartPlayerCompleter(Completer):
    def __init__(self, players_list):
        self.players_list = players_list

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        cleaned_input = clean_string(text_before_cursor)
        if not cleaned_input:
            return

        for player in self.players_list:
            if cleaned_input in clean_string(player):
                yield Completion(player, start_position=-len(text_before_cursor))


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def start_game():
    clear_screen()

    with console.status("[bold cyan]🏀 Fetching stats and picking a mystery player...", spinner="dots"):
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT player FROM View_PlayerStats_Formatted;")
        all_players = [row.player for row in cursor.fetchall() if row.player]

        eligible_query = """
        SELECT v.player 
        FROM View_PlayerStats_Formatted v
        LEFT JOIN Awards a ON v.player = a.player
        LEFT JOIN AllStars al ON v.player = al.player
        GROUP BY v.player 
        HAVING MAX(v.PPG) >= 15.0 
           AND MAX(CAST(v.season AS INT)) >= 2006
           AND (COUNT(a.award) > 0 OR COUNT(al.season) > 0);
        """
        cursor.execute(eligible_query)
        quiz_players = [row.player for row in cursor.fetchall() if row.player]

        if not quiz_players:
            console.print("[bold red]No players found matching criteria.[/bold red]")
            return

        target_player = random.choice(quiz_players)

        query = """
        SELECT 
            season, Teams, Age, GP, GS, MP, PPG, RPG, APG, 
            TOV, STL, BLK, PF, FG_Perc, ThreeP_Perc, FT_Perc, Achievements
        FROM View_PlayerStats_Formatted 
        WHERE player = ? 
        ORDER BY season ASC;
        """
        cursor.execute(query, (target_player,))
        stats = cursor.fetchall()

    # יצירת הטבלה המעוצבת
    table = Table(
        title="✨ MYSTERY PLAYER CAREER STATS ✨",
        title_style="bold gold1",
        show_header=True,
        header_style="bold white on blue",
        border_style="bright_blue",
        expand=True,
        box=None
    )

    columns = [
        ("Season", "bold cyan"), ("Team", "bold magenta"), ("Age", "dim white"),
        ("GP", "white"), ("GS", "white"), ("MP", "white"),
        ("PPG", "bold green"), ("RPG", "green"), ("APG", "green"),
        ("TOV", "dim red"), ("STL", "bright_yellow"), ("BLK", "bright_yellow"),
        ("PF", "dim red"), ("FG%", "blue"), ("3P%", "blue"),
        ("FT%", "blue"), ("Awards & Honors", "bold yellow")
    ]
    for col_name, col_style in columns:
        table.add_column(col_name, style=col_style, justify="center")

    for row in stats:
        ppg_val = format_val(row[6])
        if ppg_val != "-" and float(ppg_val) >= 20.0:
            ppg_display = f"[bold gold1]{ppg_val}[/bold gold1]"
        else:
            ppg_display = ppg_val

        achievements_val = format_val(row[16])
        if achievements_val != "-":
            achievements_display = f"[bold italic cyan]{achievements_val}[/bold italic cyan]"
        else:
            achievements_display = "[dim]-[/dim]"

        table.add_row(
            format_val(row[0]), format_val(row[1]), format_val(row[2]),
            format_val(row[3]), format_val(row[4]), format_val(row[5]),
            ppg_display, format_val(row[7]), format_val(row[8]),
            format_val(row[9]), format_val(row[10]), format_val(row[11]),
            format_val(row[12]), format_val(row[13], True), format_val(row[14], True),
            format_val(row[15], True), achievements_display
        )

    console.print(table)
    console.print()

    # הנחיות למשתמש בתוך פאנל
    instructions = "[bold yellow]Controls:[/bold yellow] Start typing to filter names | Use [bold cyan]ARROW KEYS[/bold cyan] for dropdown | Press [bold red]Ctrl+G[/bold red] to Give Up"
    console.print(
        Panel(Align.center(instructions), border_style="dim white", title="🎮 HOW TO PLAY", title_align="left"))
    console.print()

    # עיצוב מוגדר נכון לדרופ-דאון עם ערכי צבעים תקינים
    custom_prompt_style = Style.from_dict({
        'completion-menu.completion': 'bg:#333333 fg:#ffffff',
        'completion-menu.completion.current': 'bg:#0055ff fg:#ffffff bold',
    })

    bindings = KeyBindings()

    @bindings.add('c-g')
    def give_up_action(event):
        event.app.exit(result='GAVE_UP')

    completer = SmartPlayerCompleter(all_players)

    while True:
        try:
            user_input = prompt(
                "🏀 Guess Player Name: ",
                completer=completer,
                complete_style=CompleteStyle.COLUMN,
                key_bindings=bindings,
                complete_while_typing=True,
                style=custom_prompt_style
            )
        except KeyboardInterrupt:
            break

        if user_input == 'GAVE_UP':
            console.print()
            console.print(Panel(
                Align.center(
                    f"[bold red]🏳️ YOU GAVE UP![/bold red]\n\nThe Mystery Player was: [bold gold1]{target_player}[/bold gold1]"),
                border_style="red"
            ))
            break

        if clean_string(user_input) == clean_string(target_player):
            console.print()
            console.print(Panel(
                Align.center(
                    f"[bold green]🎉 BOOM! YOU GOT IT RIGHT! 🎉[/bold green]\n\nIt was indeed [bold gold1]{target_player}[/bold gold1]!"),
                border_style="green"
            ))
            break

        if user_input.strip() != "":
            console.print(f"[bold red]❌ '{user_input}' is incorrect.[/bold red] Try again!")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    start_game()