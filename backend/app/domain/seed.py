"""Baseline data and the repeatable reset (Section 5.5).

Everything here is fixed data: no random ids, no wall-clock-dependent values, so two resets with
the same inputs produce identical public state. The four sports are stored as ordinary rows in the
same schema as POST /audit/v1/sports; runtime logic reads them like any other sport.
"""
from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from ..core import ports
from ..core.errors import DomainError
from ..core.security import hash_password
from ..core.validation import Fields, is_int

DEFAULT_SEED = 42
DEFAULT_STOCK = {"var-jersey-001-M": 1, "var-jersey-001-L": 5}
RESET_LOCK = 7002
DEMO_PASSWORD = "Nascon@26"
FULL_TIE_BREAK = ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]
LIVE_MATCH_ID = "match-001"

SPORTS: list[tuple[str, str, dict]] = [
    ("football", "Football", {
        "scoring_model": "event", "periods": {"count": 2, "duration_minutes": 45},
        "scoring_events": {"goal": {"points": 1}}, "draw_allowed": True,
        "overtime": {"policy": "none"}, "tie_break_order": FULL_TIE_BREAK,
        "roster": {"min_squad_size": 11, "max_squad_size": 25, "required_positions": {"gk": 1}},
    }),
    ("basketball", "Basketball", {
        "scoring_model": "event", "periods": {"count": 4, "duration_minutes": 12},
        "scoring_events": {"free_throw": {"points": 1}, "two_pointer": {"points": 2},
                           "three_pointer": {"points": 3}},
        "draw_allowed": False, "overtime": {"policy": "extra_time", "duration_minutes": 5},
        "tie_break_order": FULL_TIE_BREAK,
        "roster": {"min_squad_size": 5, "max_squad_size": 15, "required_positions": {}},
    }),
    ("cricket", "Cricket", {
        "scoring_model": "innings",
        "periods": {"innings_per_team": 1, "overs_per_innings": 20, "balls_per_over": 6,
                    "wickets_per_innings": 10},
        "scoring_events": {
            "dot_ball": {"runs": 0, "legal_ball": True, "wicket": False},
            "single": {"runs": 1, "legal_ball": True, "wicket": False},
            "two": {"runs": 2, "legal_ball": True, "wicket": False},
            "four": {"runs": 4, "legal_ball": True, "wicket": False},
            "six": {"runs": 6, "legal_ball": True, "wicket": False},
            "wide": {"runs": 1, "legal_ball": False, "wicket": False},
            "no_ball": {"runs": 1, "legal_ball": False, "wicket": False},
            "wicket": {"runs": 0, "legal_ball": True, "wicket": True},
        },
        "draw_allowed": True, "overtime": {"policy": "super_over"}, "tie_break_order": FULL_TIE_BREAK,
        "roster": {"min_squad_size": 11, "max_squad_size": 18, "required_positions": {"wicketkeeper": 1}},
    }),
    ("esports", "Esports", {
        "scoring_model": "round", "periods": {"best_of": 3},
        "scoring_events": {"round_win": {"rounds": 1}}, "draw_allowed": False,
        "overtime": {"policy": "none"}, "tie_break_order": FULL_TIE_BREAK,
        "roster": {"min_squad_size": 5, "max_squad_size": 8, "required_positions": {}},
    }),
]

TENANTS = [
    ("tenant-alpha", "Alpha Sports",
     {"logo_url": None, "primary_color": "#0B5FFF", "secondary_color": "#FFB703", "display_name": "Alpha Sports"}),
    ("tenant-beta", "Beta Athletics",
     {"logo_url": None, "primary_color": "#2A9D8F", "secondary_color": "#E76F51", "display_name": "Beta Athletics"}),
]

LEAGUES = [("league-alpha-1", "tenant-alpha", "Alpha Premier League"),
           ("league-alpha-2", "tenant-alpha", "Alpha Division Two"),
           ("league-beta-1", "tenant-beta", "Beta Championship")]

CLUBS = [
    ("club-alpha-1", "tenant-alpha", "Alpha FC", {"name": "Alpha Stadium", "lat": 33.6844, "lng": 73.0479},
     {"instagram": "@alphafc", "x": "@alphafc"}),
    ("club-alpha-2", "tenant-alpha", "Alpha United", {"name": "United Park", "lat": 33.7294, "lng": 73.0931},
     {"instagram": "@alphaunited", "x": "@alphaunited"}),
    ("club-beta-1", "tenant-beta", "Beta Rovers", {"name": "Rovers Ground", "lat": 31.5204, "lng": 74.3587},
     {"instagram": "@betarovers", "x": "@betarovers"}),
]

PLAYERS = [("player-alpha-1", "club-alpha-1", "tenant-alpha", "Alpha Player One"),
           ("player-alpha-2", "club-alpha-2", "tenant-alpha", "Alpha Player Two"),
           ("player-beta-1", "club-beta-1", "tenant-beta", "Beta Player One")]

# The mobile demo follows these IDs from bootstrap -> standings/match/club -> roster history.
# Keep them deterministic so /reset always restores the same navigable live-data graph.
DOMAIN_LEAGUES = [
    {
        "league_id": "league-alpha-1", "sport_id": "football",
        "teams": ["club-alpha-1", "club-alpha-2"],
        "fixtures": [{"match_id": LIVE_MATCH_ID, "home": "club-alpha-1", "away": "club-alpha-2"}],
    },
    {
        "league_id": "league-alpha-2", "sport_id": "football",
        "teams": ["club-alpha-1", "club-alpha-2"], "fixtures": [],
    },
    {
        "league_id": "league-beta-1", "sport_id": "football",
        "teams": ["club-beta-1", "club-beta-guest"], "fixtures": [],
    },
]

ROSTER_BASELINE = {
    "league": {
        "league_id": "league-alpha-1", "tenant_id": "tenant-alpha", "sport_id": "football",
        "transfer_window": {"open": "2020-01-01", "close": "2099-12-31"},
        "required_positions": {},
    },
    "squads": [
        {"squad_id": "squad-alpha-1", "club_id": "club-alpha-1", "tenant_id": "tenant-alpha",
         "name": "Alpha FC First Team"},
        {"squad_id": "squad-alpha-2", "club_id": "club-alpha-2", "tenant_id": "tenant-alpha",
         "name": "Alpha United First Team"},
    ],
    "players": [
        {"player_id": "player-alpha-1", "name": "Alpha Player One", "position": "forward",
         "squad_id": "squad-alpha-1", "role": "captain"},
        {"player_id": "player-alpha-2", "name": "Alpha Player Two", "position": "defender",
         "squad_id": "squad-alpha-2", "role": "captain"},
    ],
    "matches_in_progress": [
        {"match_id": LIVE_MATCH_ID, "home_squad_id": "squad-alpha-1", "away_squad_id": "squad-alpha-2"},
    ],
}

# (user_id, email, role, display_name, tenant, league, club, player)
USERS = [
    ("user-admin", "admin@nascon.test", "super_admin", "Platform Admin", None, None, None, None),
    ("user-organizer", "organizer@nascon.test", "league_organizer", "League Organizer",
     "tenant-alpha", "league-alpha-1", None, None),
    ("user-manager", "manager@nascon.test", "club_manager", "Club Manager",
     "tenant-alpha", None, "club-alpha-1", None),
    ("user-player", "player@nascon.test", "player", "Alpha Player One",
     "tenant-alpha", None, "club-alpha-1", "player-alpha-1"),
    ("user-viewer", "viewer@nascon.test", "viewer", "General Viewer", "tenant-alpha", None, None, None),
]

TRUNCATE = (
    "TRUNCATE outbox, offline_actions, roster_requests, roster_audit, roster_matches, roster_players,"
    " roster_squads, roster_leagues, order_items, orders, price_schedule, discount_codes, variants,"
    " products, users, ref_players, ref_clubs, ref_leagues, sports, tenants, seed_state"
    " RESTART IDENTITY CASCADE"
)


def parse_reset_body(body: dict) -> tuple[int, dict[str, int]]:
    f = Fields()
    seed = body.get("seed", DEFAULT_SEED)
    if seed is None:
        seed = DEFAULT_SEED
    if not is_int(seed):
        f.add("seed")
    stock_in = body.get("stock")
    stock = dict(DEFAULT_STOCK)
    if stock_in is not None:
        if not isinstance(stock_in, dict):
            f.add("stock")
        else:
            for k, v in stock_in.items():
                if not is_int(v) or v < 0:
                    f.add("stock")
                    f.add(str(k))
                elif k in stock:
                    stock[k] = v
    f.check()
    return seed, stock


def reset(conn, seed: int = DEFAULT_SEED, stock: dict[str, int] | None = None) -> dict[str, Any]:
    """Wipe and re-create the baseline inside the caller's transaction, under an exclusive lock."""
    stock = dict(DEFAULT_STOCK if stock is None else stock)
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (RESET_LOCK,))
    conn.execute(TRUNCATE)
    conn.execute("ALTER SEQUENCE payment_seq RESTART WITH 1")
    conn.execute("ALTER SEQUENCE roster_audit_seq RESTART WITH 1")

    for tid, name, branding in TENANTS:
        conn.execute("INSERT INTO tenants (tenant_id, name, branding) VALUES (%s,%s,%s)",
                     (tid, name, Jsonb(branding)))
    for sid, name, cfg in SPORTS:
        conn.execute("INSERT INTO sports (sport_id, name, config) VALUES (%s,%s,%s)",
                     (sid, name, Jsonb(cfg)))
    for lid, tid, name in LEAGUES:
        conn.execute("INSERT INTO ref_leagues (league_id, tenant_id, name, sport_id) VALUES (%s,%s,%s,'football')",
                     (lid, tid, name))
    for cid, tid, name, venue, social in CLUBS:
        staff = [{"role": "coach", "name": f"{name} Coach"}, {"role": "manager", "name": f"{name} Manager"},
                 {"role": "physio", "name": f"{name} Physio"}]
        history = [{"season": "2025", "played": 30, "won": 18, "drawn": 6, "lost": 6}]
        branding = next(b for t, _, b in TENANTS if t == tid)
        conn.execute(
            "INSERT INTO ref_clubs (club_id, tenant_id, name, venue, social, staff, history, branding)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, tid, name, Jsonb(venue), Jsonb(social), Jsonb(staff), Jsonb(history), Jsonb(branding)))
    for pid, cid, tid, name in PLAYERS:
        conn.execute("INSERT INTO ref_players (player_id, club_id, tenant_id, name) VALUES (%s,%s,%s,%s)",
                     (pid, cid, tid, name))
    for uid, email, role, display, tid, lid, cid, pid in USERS:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, role, display_name, tenant_id, league_id,"
            " club_id, player_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, email, hash_password(DEMO_PASSWORD, email), role, display, tid, lid, cid, pid))

    conn.execute(
        "INSERT INTO products (product_id, tenant_id, club_id, name, category, description)"
        " VALUES ('prod-jersey-001','tenant-alpha','club-alpha-1','Alpha FC Home Jersey','apparel',"
        " 'Official home jersey')")
    for vid, size in (("var-jersey-001-M", "M"), ("var-jersey-001-L", "L")):
        conn.execute(
            "INSERT INTO variants (variant_id, product_id, attributes, price_minor, currency, stock, reserved)"
            " VALUES (%s,'prod-jersey-001',%s,450000,'PKR',%s,0)",
            (vid, Jsonb({"size": size, "color": "blue"}), stock[vid]))
    conn.execute("INSERT INTO discount_codes (code, percent, active) VALUES ('WELCOME10', 10, true)")

    conn.execute("INSERT INTO seed_state (id, seed) VALUES (1, %s)", (seed,))
    hooks = ports.run_reset_hooks(conn, seed)       # scoring/standings owners clear their own state
    _seed_mobile_graph(conn, seed)
    return {
        "status": "reset_complete", "seed": seed, "sports": [s[0] for s in SPORTS],
        "tenants": [t[0] for t in TENANTS], "stock": {k: stock[k] for k in DEFAULT_STOCK},
        "_hooks": hooks,
    }


def _seed_mobile_graph(conn, seed: int) -> None:
    """Restore the connected records exercised by the live mobile judging flows."""
    domain = ports.scoring()
    register = getattr(domain, "register_league", None)
    append = getattr(domain, "append_event", None)
    if not callable(register) or not callable(append):
        return

    for league in DOMAIN_LEAGUES:
        register(conn, {
            **league,
            "points": {"win": 3, "draw": 1, "loss": 0},
            "qualification": {"spots": 1},
            "lots_seed": seed,
        })

    for event_id, type_, payload in (
        ("match-001-start", "match_start", {}),
        ("match-001-goal-home-1", "score", {"team_id": "club-alpha-1", "event_type": "goal"}),
        ("match-001-goal-away-1", "score", {"team_id": "club-alpha-2", "event_type": "goal"}),
        ("match-001-goal-home-2", "score", {"team_id": "club-alpha-1", "event_type": "goal"}),
    ):
        append(conn, {"event_id": event_id, "match_id": LIVE_MATCH_ID, "type": type_, "payload": payload})

    from . import roster
    roster.setup(conn, ROSTER_BASELINE)
    conn.execute("UPDATE products SET pinned_match_id=%s WHERE product_id='prod-jersey-001'", (LIVE_MATCH_ID,))


def is_seeded(conn) -> bool:
    return conn.execute("SELECT 1 FROM seed_state WHERE id=1").fetchone() is not None


def last_seed(conn) -> int:
    row = conn.execute("SELECT seed FROM seed_state WHERE id=1").fetchone()
    return row["seed"] if row else DEFAULT_SEED
