"""
Seed All Databases — Algerian Food Data in French

Seeds both PostgreSQL (backend) and SQLite (AI) with authentic
Algerian cuisine data. Idempotent — skips if data already exists.

Usage:
    POSTGRES_URL=postgresql://user:pass@host:5432/db \
    AI_SQLITE_PATH=/data/inventory.db \
    python seed_all.py
"""

import asyncio
import json
import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.sql import insert, delete

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("seed")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
NOW = datetime.now(timezone.utc)

POSTGRES_URL = os.environ["POSTGRES_URL"]
AI_SQLITE_PATH = os.environ.get("AI_SQLITE_PATH", "/data/inventory.db")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESTAURANTS = [
    {
        "name": "Le Jardin d'Alger",
        "phone": "021 23 45 67",
        "email": "jardin.alger@mayda.dz",
        "description": "Au cœur d'Alger, découvrez une cuisine algéroise traditionnelle préparée avec des produits frais du terroir. Ambiance chaleureuse et élégante.",
        "operatingHours": {
            "monday": "09:00-23:00",
            "tuesday": "09:00-23:00",
            "wednesday": "09:00-23:00",
            "thursday": "09:00-23:00",
            "friday": "09:00-23:00",
            "saturday": "10:00-00:00",
            "sunday": "10:00-22:00",
        },
    },
    {
        "name": "El Bahia",
        "phone": "041 34 56 78",
        "email": "bahia@mayda.dz",
        "description": "Spécialités oranaises dans un cadre méditerranéen. Notre chef vous fait voyager à travers les saveurs de l'Ouest algérien.",
        "operatingHours": {
            "monday": "09:00-23:00",
            "tuesday": "09:00-23:00",
            "wednesday": "09:00-23:00",
            "thursday": "09:00-23:00",
            "friday": "14:00-00:00",
            "saturday": "10:00-00:00",
            "sunday": "10:00-22:00",
        },
    },
    {
        "name": "L'Oasis du Sud",
        "phone": "029 45 67 89",
        "email": "oasis.sud@mayda.dz",
        "description": "Voyage culinaire au cœur du Sahara. Saveurs authentiques du grand sud algérien dans un décor nomade et enchanteur.",
        "operatingHours": {
            "monday": "10:00-22:00",
            "tuesday": "10:00-22:00",
            "wednesday": "10:00-22:00",
            "thursday": "10:00-23:00",
            "friday": "10:00-23:00",
            "saturday": "10:00-23:00",
            "sunday": "11:00-21:00",
        },
    },
    {
        "name": "Dar El Kenza",
        "phone": "031 56 78 90",
        "email": "kenza.constantine@mayda.dz",
        "description": "Gastronomie constantinoise raffinée dans une demeure traditionnelle. Une expérience unique au cœur de Constantine.",
        "operatingHours": {
            "monday": "12:00-23:00",
            "tuesday": "12:00-23:00",
            "wednesday": "12:00-23:00",
            "thursday": "12:00-00:00",
            "friday": "12:00-00:00",
            "saturday": "10:00-00:00",
            "sunday": "10:00-22:00",
        },
    },
    {
        "name": "Khaymat al Hamich",
        "phone": "039 67 89 01",
        "email": "khaymat.hamich@mayda.dz",
        "description": "Campement bédouin authentique aux portes du Sahara. Dîners sous les étoiles, méchoui traditionnel et musique gnawa. Une expérience immersive unique en Algérie.",
        "operatingHours": {
            "monday": "17:00-01:00",
            "tuesday": "17:00-01:00",
            "wednesday": "17:00-01:00",
            "thursday": "17:00-01:00",
            "friday": "17:00-02:00",
            "saturday": "16:00-02:00",
            "sunday": "17:00-00:00",
        },
    },
]

USERS = {
    "admin": {
        "email": "admin@mayda.dz",
        "phone": 700000001,
        "firstName": "Yasmine",
        "lastName": "Mansouri",
        "password": "admin123456",
        "role": "ADMIN",
    },
    "managers": [
        {
            "firstName": "Karim",
            "lastName": "Benaïssa",
            "email": "karim.benaissa@mayda.dz",
            "phone": 711111111,
            "ri": 0,
        },
        {
            "firstName": "Nadia",
            "lastName": "Toumi",
            "email": "nadia.toumi@mayda.dz",
            "phone": 711111112,
            "ri": 1,
        },
        {
            "firstName": "Sami",
            "lastName": "Guerroudj",
            "email": "sami.guerroudj@mayda.dz",
            "phone": 711111113,
            "ri": 2,
        },
        {
            "firstName": "Inès",
            "lastName": "Boukhemis",
            "email": "ines.boukhemis@mayda.dz",
            "phone": 711111114,
            "ri": 3,
        },
        {
            "firstName": "Yanis",
            "lastName": "Messaoudi",
            "email": "yanis.messaoudi@mayda.dz",
            "phone": 711111115,
            "ri": 4,
        },
    ],
    "staff": [
        {"firstName": "Ahmed", "lastName": "Zerrouki", "phone": 722222221, "role": "WAITER"},
        {"firstName": "Fatima", "lastName": "Amirouche", "phone": 722222222, "role": "WAITER"},
        {"firstName": "Hocine", "lastName": "Mokhtar", "phone": 722222223, "role": "CHEF"},
        {"firstName": "Lynda", "lastName": "Slimani", "phone": 722222224, "role": "CHEF"},
        {"firstName": "Rachid", "lastName": "Bouhafs", "phone": 722222225, "role": "WAITER"},
        {"firstName": "Samira", "lastName": "Belkacem", "phone": 722222226, "role": "WAITER"},
        {"firstName": "Yacine", "lastName": "Khelifa", "phone": 722222227, "role": "CHEF"},
        {"firstName": "Warda", "lastName": "Bouchareb", "phone": 722222228, "role": "CHEF"},
        {"firstName": "Hakim", "lastName": "Bensalem", "phone": 722222229, "role": "WAITER"},
        {"firstName": "Malika", "lastName": "Oussedik", "phone": 722222230, "role": "WAITER"},
        {"firstName": "Sofiane", "lastName": "Ait Ali", "phone": 722222231, "role": "CHEF"},
        {"firstName": "Nora", "lastName": "Hadjadj", "phone": 722222232, "role": "CHEF"},
        {"firstName": "Redouane", "lastName": "Kaci", "phone": 722222233, "role": "WAITER"},
        {"firstName": "Zahra", "lastName": "Mokhtari", "phone": 722222234, "role": "WAITER"},
        {"firstName": "Aziz", "lastName": "Benmohamed", "phone": 722222235, "role": "CHEF"},
        {"firstName": "Karima", "lastName": "Toubal", "phone": 722222236, "role": "CHEF"},
        {"firstName": "Lamine", "lastName": "Dib", "phone": 722222237, "role": "WAITER"},
        {"firstName": "Nassima", "lastName": "Hallal", "phone": 722222238, "role": "WAITER"},
        {"firstName": "Farid", "lastName": "Boualem", "phone": 722222239, "role": "CHEF"},
        {"firstName": "Kenza", "lastName": "Mazouni", "phone": 722222240, "role": "CHEF"},
    ],
    "clients": [
        {"firstName": "Mohamed", "lastName": "Said", "email": "mohamed.said@email.com", "phone": 733333331},
        {"firstName": "Sarah", "lastName": "Mebarki", "email": "sarah.mebarki@email.com", "phone": 733333332},
        {"firstName": "Amine", "lastName": "Hadj", "email": "amine.hadj@email.com", "phone": 733333333},
        {"firstName": "Lina", "lastName": "Boumediene", "email": "lina.boumediene@email.com", "phone": 733333334},
        {"firstName": "Reda", "lastName": "Ziani", "email": "reda.ziani@email.com", "phone": 733333335},
        {"firstName": "Meriem", "lastName": "Akli", "email": "meriem.akli@email.com", "phone": 733333336},
    ],
}

CLIENT_ADDRESSES = [
    {"street": "42 Rue Didouche Mourad", "city": "Alger"},
    {"street": "15 Boulevard Ourida Meddad", "city": "Oran"},
    {"street": "7 Cité des Martyrs", "city": "Constantine"},
    {"street": "28 Rue Larbi Ben M'hidi", "city": "Annaba"},
    {"street": "3 Avenue de l'ALN", "city": "Tizi Ouzou"},
    {"street": "55 Rue Abane Ramdane", "city": "Blida"},
]

MENU_CATEGORIES = [
    ("Entrées", "Hors-d'œuvre et soupes traditionnelles", 1),
    ("Salades", "Salades fraîches et composées", 2),
    ("Plats Principaux", "Spécialités algériennes authentiques", 3),
    ("Spécialités Régionales", "Plats typiques de chaque région d'Algérie", 4),
    ("Pâtisseries", "Pâtisseries traditionnelles algériennes", 5),
    ("Desserts", "Desserts et douceurs", 6),
    ("Boissons Chaudes", "Thé, café et boissons traditionnelles", 7),
    ("Boissons Froides", "Jus frais et boissons rafraîchissantes", 8),
]

# Dishes organised by category — all Algerian cuisine in French
DISHES = {  # each entry: (name, description, price_dzd, prep_min, popularity)
    "Entrées": [
        (
            "Chorba Frik",
            "Soupe traditionnelle algérienne au frik (blé vert concassé), tomates, pois chiches et viande d'agneau",
            4.50,
            15,
            4.8,
        ),
        (
            "Chorba Beïda",
            "Soupe blanche au poulet, cannelle et citron, spécialité constantinoise",
            4.00,
            12,
            4.6,
        ),
        (
            "Harira",
            "Soupe algérienne riche en tomates, pois chiches, lentilles et coriandre",
            4.50,
            20,
            4.7,
        ),
        (
            "Chourba Djedj",
            "Soupe de poulet aux vermicelles et légumes frais",
            3.50,
            12,
            4.5,
        ),
        (
            "Bourek Annabi",
            "Brick à la viande hachée, oignons et persil, spécialité d'Annaba",
            5.00,
            10,
            4.9,
        ),
        (
            "Mhadjeb",
            "Crêpe feuilletée farcie aux oignons, tomates et poivrons",
            3.00,
            8,
            4.6,
        ),
        (
            "Karantika",
            "Flan de pois chiches cuit au four, spécialité oranaise",
            2.50,
            5,
            4.5,
        ),
        (
            "Tadjine Malsouf",
            "Omelette aux légumes et à la viande hachée",
            4.00,
            12,
            4.4,
        ),
    ],
    "Salades": [
        (
            "Salade Mechouia",
            "Salade de poivrons grillés, tomates, oignons et ail, assaisonnée à l'huile d'olive",
            3.00,
            10,
            4.7,
        ),
        (
            "Salade Djari",
            "Salade de mloukhia (corète) aux olives et citron",
            3.50,
            8,
            4.3,
        ),
        (
            "Chlata Felfel",
            "Salade de poivrons verts frits à l'huile d'olive",
            2.50,
            8,
            4.5,
        ),
        (
            "Felfel Mahchi",
            "Poivrons farcis à la viande hachée et aux épices",
            5.00,
            15,
            4.6,
        ),
        ("Bakbouka", "Salade d'escargots à la menthe et aux épices", 4.00, 12, 4.2),
    ],
    "Plats Principaux": [
        (
            "Couscous Royal",
            "Couscous aux légumes de saison, merguez, poulet et mouton",
            8.00,
            30,
            4.9,
        ),
        (
            "Couscous Bel Hout",
            "Couscous au poisson, légumes et sauce tomate épicée",
            9.00,
            35,
            4.8,
        ),
        (
            "Couscous Tchicha",
            "Couscous à la tchicha (orge concassée) et légumes",
            7.00,
            35,
            4.6,
        ),
        (
            "Rechta",
            "Pâtes fraîches algériennes au poulet, pois chiches et navets, sauce blanche parfumée",
            7.00,
            35,
            4.9,
        ),
        ("Rechta Mhamsa", "Rechta aux œufs durs et cannelle", 7.50, 30, 4.7),
        (
            "Chakhchoukha",
            "Galette émiettée à la sauce tomate, légumes et viande d'agneau, spécialité constantinoise",
            7.00,
            40,
            4.8,
        ),
        ("Chakhchoukha Djedj", "Chakhchoukha au poulet et pois chiches", 6.50, 35, 4.6),
        (
            "Berkoukes",
            "Gros couscous aux fèves, pois chiches et viande séchée (khlii)",
            7.50,
            45,
            4.7,
        ),
        (
            "Tlitli",
            "Petites pâtes algériennes au poulet, pois chiches et courgettes",
            6.00,
            30,
            4.6,
        ),
        (
            "Tride",
            "Crêpes superposées à la sauce blanche et au poulet, arrosées de beurre fondu",
            7.00,
            40,
            4.7,
        ),
        (
            "Lham Lahlou",
            "Viande d'agneau sucrée aux pruneaux, abricots secs et amandes",
            8.50,
            45,
            4.8,
        ),
        (
            "Tadjine Zitoune",
            "Tadjine de poulet aux olives vertes et citron confit",
            7.00,
            30,
            4.8,
        ),
        (
            "M'chemmel",
            "Poulet rôti aux olives, citron confit et épices douces",
            7.50,
            35,
            4.7,
        ),
        (
            "Chtitha",
            "Viande d'agneau cuite lentement dans une sauce aux herbes et à l'huile d'olive",
            8.00,
            50,
            4.5,
        ),
        (
            "Marqa Bel Assfour",
            "Ragoût de viande aux herbes fraîches, petits pois et artichauts",
            7.00,
            40,
            4.6,
        ),
        (
            "Dolma",
            "Légumes farcis (courgettes, poivrons, tomates) à la viande hachée et au riz",
            6.50,
            35,
            4.9,
        ),
        (
            "Mechoui",
            "Agneau rôti à la broche, servi avec du sel, du cumin et du pain traditionnel",
            10.00,
            60,
            4.9,
        ),
        (
            "Merguez",
            "Saucisses épicées grillées, servies avec frites et sauce harissa",
            5.00,
            12,
            4.7,
        ),
        (
            "Mderbel",
            "Purée de courgettes à la viande hachée et aux épices",
            5.50,
            20,
            4.4,
        ),
        (
            "Chouikh",
            "Ragoût de viande séchée (khlii) aux oignons et tomates",
            6.00,
            25,
            4.3,
        ),
    ],
    "Spécialités Régionales": [
        (
            "Couscous Kabyle (Seksou)",
            "Couscous aux fèves, petits pois, olives et poulet, spécialité de Kabylie",
            7.50,
            35,
            4.8,
        ),
        (
            "Aghroum n'Tchicha",
            "Pain d'orge kabyle aux légumes et à l'huile d'olive",
            5.00,
            25,
            4.5,
        ),
        (
            "Rfis",
            "Semoule grillée au beurre et au miel, spécialité des Aurès",
            4.00,
            15,
            4.4,
        ),
        (
            "Couscous Tlemcénien",
            "Couscous fin aux raisins secs, cannelle et amandes",
            8.00,
            35,
            4.7,
        ),
        (
            "Djari (Mloukhia)",
            "Sauce verte à la corète servie avec de la viande et du pain, spécialité annabie",
            7.00,
            50,
            4.6,
        ),
        (
            "Taguella",
            "Pain cuit sous les cendres, spécialité saharienne, servi avec du thé",
            3.50,
            20,
            4.5,
        ),
        (
            "Mhancha Kabyle",
            "Galette farcie aux oignons, pommes de terre et herbes",
            4.00,
            15,
            4.6,
        ),
    ],
    "Pâtisseries": [
        (
            "Baklawa",
            "Feuilleté aux amandes et au miel, parfumé à l'eau de fleur d'oranger",
            3.00,
            5,
            4.9,
        ),
        (
            "Makroud",
            "Gâteau de semoule aux dattes, frit et trempé dans le miel",
            2.50,
            5,
            4.8,
        ),
        (
            "Griwech",
            "Pâtisserie frite en forme de rosace, au miel et au sésame",
            2.50,
            8,
            4.7,
        ),
        (
            "Zlabia",
            "Beignet au miel de forme torsadée, spécialité ramadhanesque",
            2.00,
            5,
            4.6,
        ),
        ("Sfenj", "Beignet algérien moelleux, saupoudré de sucre glace", 1.50, 5, 4.5),
        ("Tamina", "Semoule sucrée au beurre, miel et caroube", 2.00, 5, 4.4),
        ("M'kacher", "Crêpe feuilletée sucrée à la semoule et au beurre", 2.50, 8, 4.5),
        ("Bradj", "Petits gâteaux à la pâte d'amande et au miel", 3.00, 5, 4.6),
        (
            "Tcharek",
            "Cornes de gazelle farcies aux amandes et à la fleur d'oranger",
            3.00,
            5,
            4.8,
        ),
        (
            "Millefuit Algérien",
            "Millefeuille à la crème pâtissière parfumée à la fleur d'oranger",
            3.50,
            5,
            4.7,
        ),
    ],
    "Desserts": [
        (
            "Baghrir",
            "Crêpe mille trous à la semoule, servie avec du miel et du beurre",
            2.50,
            8,
            4.8,
        ),
        (
            "Msemen",
            "Crêpe feuilletée algérienne, servie nature ou au miel",
            2.00,
            8,
            4.7,
        ),
        (
            "Mesfouf",
            "Couscous sucré aux raisins secs, beurre et cannelle",
            3.00,
            10,
            4.6,
        ),
        (
            "Chrik",
            "Pain au beurre parfumé à la fleur d'oranger et au miel",
            2.50,
            10,
            4.5,
        ),
        ("Lablabi", "Pudding aux pois chiches et au miel", 2.50, 5, 4.3),
    ],
    "Boissons Chaudes": [
        (
            "Thé à la Menthe",
            "Thé vert préparé à la menthe fraîche, servi avec des pignons de pin",
            1.50,
            5,
            4.9,
        ),
        (
            "Thé Aux Herbes",
            "Infusion de verveine, menthe et thym du Djurdjura",
            1.50,
            5,
            4.5,
        ),
        ("Café Turc", "Café moulu à la turque préparé dans le sable", 2.00, 8, 4.7),
        ("Café Arabica", "Café arabica torréfié à l'algéroise", 1.50, 4, 4.6),
        ("Lait de Poulette", "Lait chaud au miel et à la cannelle", 2.00, 5, 4.4),
        (
            "Hbib",
            "Infusion de plantes du sud algérien, légèrement sucrée",
            2.50,
            7,
            4.3,
        ),
    ],
    "Boissons Froides": [
        ("Jus d'Orange Frais", "Jus d'orange fraîchement pressé", 2.50, 3, 4.8),
        ("Lben", "Lait fermenté traditionnel, rafraîchissant", 1.50, 2, 4.5),
        ("Rayeb", "Yogourt liquide traditionnel", 1.50, 2, 4.4),
        ("Citronnade", "Citron pressé à la menthe fraîche", 2.00, 3, 4.6),
        ("Jus d'Abricot", "Jus d'abricot du M'zab", 2.50, 3, 4.5),
        ("Jus de Pastèque", "Jus de pastèque fraîche, spécialité d'été", 2.00, 3, 4.7),
        (
            "Cherbet",
            "Sirop traditionnel aux fruits et à l'eau de fleur d'oranger",
            2.00,
            3,
            4.5,
        ),
    ],
}

# Inventory items (ingredients for Algerian cooking)
INVENTORY = [
    # (name, unit, min_stock, unit_cost, supplier, description)
    (
        "Semoule Fine",
        "kg",
        10,
        1.50,
        "Minoterie d'Alger",
        "Semoule de blé dur fine pour couscous",
    ),
    (
        "Semoule Moyenne",
        "kg",
        15,
        1.50,
        "Minoterie d'Alger",
        "Semoule moyenne pour msemen et baghrir",
    ),
    (
        "Semoule Grosse",
        "kg",
        20,
        1.20,
        "Minoterie des Aurès",
        "Grosse semoule pour couscous royal",
    ),
    ("Farine", "kg", 20, 0.80, "Minoterie d'Alger", "Farine de blé tout usage"),
    (
        "Huile d'Olive",
        "litre",
        10,
        8.00,
        "Huilerie de Kabylie",
        "Huile d'olive extra vierge",
    ),
    ("Beurre", "kg", 8, 5.00, "Ferme Laitière de Blida", "Beurre frais"),
    (
        "Viande d'Agneau",
        "kg",
        15,
        14.00,
        "Boucherie Halal Centrale",
        "Viande d'agneau élevé en plein air",
    ),
    (
        "Viande de Bœuf",
        "kg",
        12,
        12.00,
        "Boucherie Halal Centrale",
        "Viande de bœuf locale",
    ),
    (
        "Poulet",
        "kg",
        18,
        6.00,
        "Ferme Avicole de l'Est",
        "Poulet fermier élevé au grain",
    ),
    (
        "Merguez",
        "kg",
        10,
        8.00,
        "Boucherie Traditionnelle",
        "Saucisses épicées algériennes",
    ),
    (
        "Poisson Merlan",
        "kg",
        6,
        10.00,
        "Pêcherie d'Alger",
        "Merlan frais de la Méditerranée",
    ),
    (
        "Poitrine d'Agneau Séchée",
        "kg",
        3,
        18.00,
        "Boucherie Traditionnelle",
        "Khlii (viande séchée) traditionnel",
    ),
    (
        "Pois Chiches",
        "kg",
        15,
        2.50,
        "Épices et Légumineuses Bab El Oued",
        "Pois chiches secs",
    ),
    (
        "Lentilles",
        "kg",
        10,
        2.00,
        "Épices et Légumineuses Bab El Oued",
        "Lentilles brunes",
    ),
    (
        "Fèves Sèches",
        "kg",
        12,
        2.50,
        "Épices et Légumineuses Bab El Oued",
        "Fèves décortiquées",
    ),
    ("Fèves Fraîches", "kg", 5, 3.00, "Marché de la Lyre", "Fèves fraîches de saison"),
    ("Tomates", "kg", 25, 1.50, "Marché de la Lyre", "Tomates fraîches"),
    (
        "Tomates Pelées",
        "boîte",
        20,
        1.00,
        "Conserverie d'Alger",
        "Tomates pelées en conserve",
    ),
    (
        "Concentré de Tomate",
        "kg",
        10,
        2.00,
        "Conserverie d'Alger",
        "Double concentré de tomate",
    ),
    ("Oignons", "kg", 20, 1.00, "Marché de la Lyre", "Oignons jaunes"),
    ("Ail", "kg", 5, 3.00, "Marché de la Lyre", "Ail frais du pays"),
    ("Poivrons Verts", "kg", 10, 2.00, "Marché de la Lyre", "Poivrons verts doux"),
    ("Courgettes", "kg", 10, 2.00, "Marché de la Lyre", "Courgettes fraîches"),
    ("Carottes", "kg", 15, 1.00, "Marché de la Lyre", "Carottes fraîches"),
    ("Pommes de Terre", "kg", 25, 1.00, "Marché de la Lyre", "Pommes de terre locales"),
    ("Navets", "kg", 8, 1.50, "Marché de la Lyre", "Navets frais"),
    ("Céleri", "kg", 3, 2.50, "Marché de la Lyre", "Branches de céleri frais"),
    (
        "Olives Vertes",
        "kg",
        8,
        4.00,
        "Conserverie de Kabylie",
        "Olives vertes confites",
    ),
    (
        "Citrons Confits",
        "kg",
        5,
        6.00,
        "Conserverie de Kabylie",
        "Citrons confits au sel",
    ),
    (
        "Dattes Deglet Nour",
        "kg",
        10,
        8.00,
        "Palmeraie de Tolga",
        "Dattes Deglet Nour de Tolga",
    ),
    ("Miel", "kg", 5, 12.00, "Rucher du Djurdjura", "Miel de montagne pur"),
    ("Amandes", "kg", 8, 10.00, "Fruit Secs d'Algérie", "Amandes mondées"),
    ("Noix", "kg", 5, 8.00, "Fruit Secs d'Algérie", "Noix fraîches de Kabylie"),
    (
        "Menthe Fraîche",
        "botte",
        15,
        1.00,
        "Marché de la Lyre",
        "Menthe fraîche pour le thé",
    ),
    ("Coriandre Fraîche", "botte", 15, 1.00, "Marché de la Lyre", "Coriandre fraîche"),
    ("Persil Frais", "botte", 15, 0.80, "Marché de la Lyre", "Persil plat frais"),
    ("Cumin", "kg", 3, 6.00, "Épices du Souk", "Cumin moulu"),
    ("Paprika", "kg", 3, 5.00, "Épices du Souk", "Paprika doux"),
    ("Safran", "g", 50, 30.00, "Épices du Souk", "Safran pur"),
    ("Ras El Hanout", "kg", 2, 8.00, "Épices du Souk", "Mélange d'épices algérien"),
    ("Cannelle", "kg", 2, 6.00, "Épices du Souk", "Bâtons de cannelle"),
    ("Clou de Girofle", "kg", 1, 10.00, "Épices du Souk", "Clous de girofle"),
    ("Harissa", "kg", 5, 4.00, "Condiments d'Algérie", "Pâte de piment algérienne"),
    (
        "Eau de Fleur d'Oranger",
        "litre",
        5,
        5.00,
        "Distillerie de Blida",
        "Eau de fleur d'oranger naturelle",
    ),
    ("Vermicelle", "kg", 8, 1.50, "Pâtes d'Algérie", "Vermicelle fine"),
    (
        "Pâte Feuilletée (Brick)",
        "paquet",
        20,
        2.00,
        "Pâtes d'Algérie",
        "Feuilles de brick traditionnelles",
    ),
    (
        "Œufs",
        "unité",
        60,
        0.20,
        "Ferme Avicole de l'Est",
        "Œufs de poules élevées en plein air",
    ),
    ("Lait", "litre", 15, 1.00, "Ferme Laitière de Blida", "Lait entier frais"),
    ("Fromage", "kg", 5, 6.00, "Ferme Laitière de Blida", "Fromage frais local"),
    ("Raisins Secs", "kg", 5, 5.00, "Fruit Secs d'Algérie", "Raisins secs du Sud"),
]

PROMOTIONS = [
    (
        "Happy Hour",
        "HAPPY_HOUR",
        "PERCENTAGE",
        30.0,
        0,
        30,
        "Menu du soir - réduit de 30% de 18h à 20h",
    ),
    (
        "Spécial Couscous",
        "DISCOUNT",
        "PERCENTAGE",
        15.0,
        0,
        30,
        "Réduction de 15% sur tous les couscous le vendredi",
    ),
]

LANGS = ["fr", "ar", "ber", "en", "es", "it", "de", "zh"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def hash_pw(password: str) -> str:
    return pwd_ctx.hash(password)


def random_time(h: int, m: int) -> datetime:
    return NOW.replace(hour=h, minute=m, second=0, microsecond=0)


def past_time(days_ago: int, h: int = 12, m: int = 0) -> datetime:
    return (NOW - timedelta(days=days_ago)).replace(
        hour=h, minute=m, second=0, microsecond=0
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POSTGRES SEED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def seed_postgres():
    logger.info("Seeding PostgreSQL...")

    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    meta = MetaData()
    meta.reflect(bind=engine)

    tables = meta.tables
    t_resto = tables["restaurants"]
    t_user = tables["users"]
    t_addr = tables["addresses"]
    t_table = tables["tables"]
    t_menu = tables["menus"]
    t_cat = tables["menu_categories"]
    t_dish = tables["dishes"]
    t_inv = tables["inventory"]
    t_ing_link = tables["ingredient"]
    t_promo = tables["promotions"]
    t_loyalty = tables["loyalty_cards"]
    t_order = tables["orders"]
    t_oi = tables["order_items"]
    t_review = tables["reviews"]
    t_reservation = tables["reservations"]
    t_txn = tables["loyalty_transactions"]
    t_settings = tables["platform_settings"]

    # Clear existing data — use raw psycopg2 to avoid SQLAlchemy transaction issues
    import psycopg2
    dsn = POSTGRES_URL.replace("postgresql://", "postgresql://")
    raw_conn = psycopg2.connect(dsn)
    raw_conn.set_session(autocommit=True)
    cur = raw_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    existing_count = cur.fetchone()[0]
    if existing_count > 0:
        logger.info("Existing data found (%d users), clearing before re-seed...", existing_count)
        cur.execute("TRUNCATE TABLE users CASCADE")
        cur.execute("TRUNCATE TABLE restaurants CASCADE")
        cur.execute("TRUNCATE TABLE platform_settings CASCADE")
        logger.info("Existing data cleared.")
    cur.close()
    raw_conn.close()

    # Seed in a new transactional connection
    with engine.begin() as conn:
        logger.info("Seeding fresh...")

        # ── Platform Settings ────
        conn.execute(
            t_settings.insert().values(
                id=1,
                currency="DZD",
                timezone="Africa/Algiers",
                defaultOperatingHours=json.dumps(
                    {
                        "monday": "09:00-22:00",
                        "tuesday": "09:00-22:00",
                        "wednesday": "09:00-22:00",
                        "thursday": "09:00-22:00",
                        "friday": "09:00-22:00",
                        "saturday": "10:00-23:00",
                        "sunday": "10:00-21:00",
                    }
                ),
                featureFlags=json.dumps(
                    {
                        "reservations": True,
                        "delivery": True,
                        "takeaway": True,
                        "loyalty_program": True,
                        "ai_recommendations": True,
                    }
                ),
                updatedAt=NOW,
            )
        )
        logger.info(" Platform settings seeded")

        # ── Restaurants ────
        resto_rows = []
        for r in RESTAURANTS:
            row = dict(r)
            row["operatingHours"] = json.dumps(row["operatingHours"])
            row["isActive"] = True
            row["gallery"] = []
            row["createdAt"] = NOW
            row["updatedAt"] = NOW
            resto_rows.append(row)
        for r in resto_rows:
            conn.execute(t_resto.insert().values(**r))
        resto_ids = [
            row[0]
            for row in conn.execute(
                t_resto.select().with_only_columns(t_resto.c.id).order_by(t_resto.c.id)
            ).fetchall()
        ]
        n_restos = len(resto_ids)
        logger.info(f" {n_restos} restaurants seeded")

        # ── Users ────
        user_rows = []
        # Admin
        a = USERS["admin"]
        user_rows.append(
            {
                "email": a["email"],
                "phone": a["phone"],
                "firstName": a["firstName"],
                "lastName": a["lastName"],
                "role": "ADMIN",
                "isActive": True,
                "password": hash_pw(a["password"]),
                "createdAt": NOW,
                "updatedAt": NOW,
            }
        )
        # Managers
        for mgr in USERS["managers"]:
            user_rows.append(
                {
                    "email": mgr["email"],
                    "phone": mgr["phone"],
                    "firstName": mgr["firstName"],
                    "lastName": mgr["lastName"],
                    "role": "MANAGER",
                    "isActive": True,
                    "password": hash_pw("manager123"),
                    "restaurantId": resto_ids[mgr["ri"]],
                    "createdAt": NOW,
                    "updatedAt": NOW,
                }
            )
        # Staff — 4 per restaurant
        n_restos = len(resto_ids)
        staff_roles = ["WAITER", "WAITER", "CHEF", "CHEF"]
        for ri in range(n_restos):
            for si in range(4):
                s = USERS["staff"][ri * 4 + si]
                email = (
                    f"{s['firstName'].lower()}.{s['lastName'].lower()}.r{ri}@mayda.dz"
                )
                user_rows.append(
                    {
                        "email": email,
                        "phone": s["phone"],
                        "firstName": f"{s['firstName']}",
                        "lastName": f"{s['lastName']}",
                        "role": staff_roles[si],
                        "isActive": True,
                        "password": hash_pw("staff123"),
                        "restaurantId": resto_ids[ri],
                        "createdAt": NOW,
                        "updatedAt": NOW,
                    }
                )
        # Clients
        for cl in USERS["clients"]:
            user_rows.append(
                {
                    "email": cl["email"],
                    "phone": cl["phone"],
                    "firstName": cl["firstName"],
                    "lastName": cl["lastName"],
                    "role": "CLIENT",
                    "isActive": True,
                    "password": hash_pw("client123"),
                    "createdAt": NOW,
                    "updatedAt": NOW,
                }
            )
        for u in user_rows:
            conn.execute(t_user.insert().values(**u))
        user_rows_all = conn.execute(
            t_user.select()
            .with_only_columns(t_user.c.id, t_user.c.role, t_user.c.email)
            .order_by(t_user.c.id)
        ).fetchall()
        logger.info(f" {len(user_rows_all)} users seeded")

        # ── Addresses ────
        client_users = [u for u in user_rows_all if u.role == "CLIENT"]
        for i, cu in enumerate(client_users):
            addr = CLIENT_ADDRESSES[i % len(CLIENT_ADDRESSES)]
            conn.execute(
                t_addr.insert().values(
                    userId=cu.id,
                    street=addr["street"],
                    city=addr["city"],
                    isDefault=True,
                    createdAt=NOW,
                    updatedAt=NOW,
                )
            )
        logger.info(f" {len(client_users)} addresses seeded")

        # ── Tables ────
        table_count = 0
        for ri in range(n_restos):
            for i in range(1, 16):
                cap = random.choice([2, 4, 4, 6, 8])
                conn.execute(
                    t_table.insert().values(
                        restaurantId=resto_ids[ri],
                        number=f"T{ri + 1}-{i:02d}",
                        capacity=cap,
                        isActive=True,
                        status="AVAILABLE",
                        qrCode=f"MAYDA-{ri + 1}-T{i:02d}",
                        createdAt=NOW,
                        updatedAt=NOW,
                    )
                )
                table_count += 1
        logger.info(f" {table_count} tables seeded")

        # ── Menus ────
        cat_names = [c[0] for c in MENU_CATEGORIES]
        cat_descs = [c[1] for c in MENU_CATEGORIES]
        all_menu_ids = []
        all_cat_ids = []
        all_dish_ids = []
        all_inv_ids = []
        dish_to_inv_map = {}  # dish_name → list of (inv_name, qty)

        for ri in range(n_restos):
            resto_name = RESTAURANTS[ri]["name"]
            conn.execute(
                t_menu.insert().values(
                    restaurantId=resto_ids[ri],
                    name=f"Carte {resto_name}",
                    description=f"Menu traditionnel algérien - {resto_name}",
                    isActive=True,
                    displayOrder=1,
                    createdAt=NOW,
                    updatedAt=NOW,
                )
            )
            mid = conn.execute(
                t_menu.select()
                .with_only_columns(t_menu.c.id)
                .where(t_menu.c.restaurantId == resto_ids[ri])
                .where(t_menu.c.name == f"Carte {resto_name}")
            ).scalar()
            all_menu_ids.append(mid)

            for ci, (cn, cd, _) in enumerate(MENU_CATEGORIES):
                if cn in DISHES:
                    conn.execute(
                        t_cat.insert().values(
                            menuId=mid,
                            name=cn,
                            description=cd,
                            isActive=True,
                            displayOrder=ci + 1,
                            createdAt=NOW,
                            updatedAt=NOW,
                        )
                    )
                    cat_id = conn.execute(
                        t_cat.select()
                        .with_only_columns(t_cat.c.id)
                        .where(t_cat.c.menuId == mid)
                        .where(t_cat.c.name == cn)
                    ).scalar()
                    all_cat_ids.append(cat_id)

                    for di, dish_data in enumerate(DISHES[cn]):
                        name, desc, price, prep, popular = dish_data
                        qty = random.randint(30, 150)
                        conn.execute(
                            t_dish.insert().values(
                                categoryId=cat_id,
                                name=name,
                                description=desc,
                                price=price,
                                isAvailable=True,
                                quantity=qty,
                                preparationTime=prep,
                                popularity=popular,
                                displayOrder=di + 1,
                                createdAt=NOW,
                                updatedAt=NOW,
                            )
                        )
                        dish_id = conn.execute(
                            t_dish.select()
                            .with_only_columns(t_dish.c.id)
                            .where(t_dish.c.categoryId == cat_id)
                            .where(t_dish.c.name == name)
                        ).scalar()
                        all_dish_ids.append(dish_id)

                        # Build ingredient map for later linking
                        # Each dish consumes a random selection of relevant ingredients
                        inv_keywords = {
                            "Couscous": [
                                "Semoule Grosse",
                                "Huile d'Olive",
                                "Pois Chiches",
                                "Carottes",
                                "Courgettes",
                                "Tomates",
                                "Oignons",
                                "Navets",
                            ],
                            "Chorba": [
                                "Vermicelle",
                                "Tomates",
                                "Oignons",
                                "Pois Chiches",
                                "Coriandre Fraîche",
                                "Cumin",
                                "Viande d'Agneau",
                            ],
                            "Harira": [
                                "Tomates",
                                "Lentilles",
                                "Pois Chiches",
                                "Coriandre Fraîche",
                                "Cumin",
                                "Concentré de Tomate",
                            ],
                            "Bourek": [
                                "Pâte Feuilletée (Brick)",
                                "Viande de Bœuf",
                                "Oignons",
                                "Persil Frais",
                                "Cumin",
                            ],
                            "Mhadjeb": [
                                "Semoule Fine",
                                "Tomates",
                                "Oignons",
                                "Poivrons Verts",
                                "Huile d'Olive",
                            ],
                            "Rechta": [
                                "Semoule Fine",
                                "Poulet",
                                "Pois Chiches",
                                "Navets",
                                "Cannelle",
                            ],
                            "Chakhchoukha": [
                                "Farine",
                                "Tomates",
                                "Poivrons Verts",
                                "Viande d'Agneau",
                                "Pois Chiches",
                                "Ras El Hanout",
                            ],
                            "Berkoukes": [
                                "Semoule Grosse",
                                "Fèves Sèches",
                                "Pois Chiches",
                                "Viande d'Agneau",
                                "Tomates",
                            ],
                            "Baklawa": [
                                "Amandes",
                                "Miel",
                                "Eau de Fleur d'Oranger",
                                "Beurre",
                            ],
                            "Makroud": [
                                "Semoule Fine",
                                "Dattes",
                                "Miel",
                                "Huile d'Olive",
                            ],
                            "Baghrir": [
                                "Semoule Fine",
                                "Miel",
                                "Beurre",
                                "Eau de Fleur d'Oranger",
                            ],
                            "Thé": ["Menthe Fraîche"],
                            "Tadjine": [
                                "Viande d'Agneau",
                                "Olives Vertes",
                                "Citrons Confits",
                                "Huile d'Olive",
                                "Safran",
                            ],
                            "Dolma": [
                                "Viande de Bœuf",
                                "Riz",
                                "Courgettes",
                                "Poivrons Verts",
                                "Tomates",
                            ],
                            "Mechoui": ["Viande d'Agneau", "Cumin", "Sel"],
                            "Merguez": ["Merguez", "Harissa"],
                            "Lham": [
                                "Viande d'Agneau",
                                "Pruneaux",
                                "Amandes",
                                "Cannnelle",
                            ],
                            "Msemen": ["Semoule Fine", "Beurre", "Huile d'Olive"],
                            "Sfenj": ["Farine", "Huile d'Olive"],
                            "Lben": ["Lait"],
                            "Tlitli": [
                                "Semoule Fine",
                                "Poulet",
                                "Pois Chiches",
                                "Courgettes",
                                "Cannelle",
                            ],
                            "Zlabia": ["Farine", "Miel", "Eau de Fleur d'Oranger"],
                            "Griwech": ["Semoule Fine", "Beurre", "Miel"],
                            "Tride": ["Farine", "Poulet", "Beurre", "Cannelle"],
                            "M'chemmel": [
                                "Poulet",
                                "Olives Vertes",
                                "Citrons Confits",
                                "Huile d'Olive",
                            ],
                            "Djari": [
                                "Coriandre Fraîche",
                                "Huile d'Olive",
                                "Viande de Bœuf",
                            ],
                            "Taguella": ["Farine", "Sel"],
                            "Karantika": ["Pois Chiches", "Œufs", "Cumin"],
                            "Chtitha": [
                                "Viande d'Agneau",
                                "Persil Frais",
                                "Huile d'Olive",
                            ],
                            "Chouikh": [
                                "Poitrine d'Agneau Séchée",
                                "Oignons",
                                "Tomates",
                            ],
                            "Mderbel": ["Courgettes", "Viande de Bœuf", "Tomates"],
                            "Chourba": [
                                "Poulet",
                                "Vermicelle",
                                "Tomates",
                                "Carottes",
                                "Cannelle",
                            ],
                            "Chrik": [
                                "Farine",
                                "Beurre",
                                "Miel",
                                "Eau de Fleur d'Oranger",
                            ],
                            "Mesfouf": [
                                "Semoule Grosse",
                                "Raisins Secs",
                                "Beurre",
                                "Cannelle",
                            ],
                            "Rfis": ["Semoule Fine", "Beurre", "Miel", "Dattes"],
                            "M'kacher": ["Semoule Fine", "Beurre", "Miel"],
                            "Mhancha": [
                                "Semoule Fine",
                                "Oignons",
                                "Pommes de Terre",
                                "Huile d'Olive",
                            ],
                            "Tcharek": ["Amandes", "Eau de Fleur d'Oranger", "Miel"],
                            "Felfel": ["Poivrons Verts", "Huile d'Olive", "Ail"],
                            "Bakbouka": ["Menthe Fraîche", "Huile d'Olive", "Cumin"],
                            "Salade Mechouia": [
                                "Poivrons Verts",
                                "Tomates",
                                "Ail",
                                "Huile d'Olive",
                            ],
                        }
                        # Match dish to ingredients
                        matched = []
                        for kw, ing_names in inv_keywords.items():
                            if kw.lower() in name.lower():
                                matched.extend(ing_names)
                        if not matched:
                            # Fallback: generic
                            matched = ["Huile d'Olive", "Sel", "Cumin"]
                        dish_to_inv_map[name] = list(set(matched))

        # ── Inventory ────
        for ri in range(n_restos):
            for inv_item in INVENTORY:
                iname, iunit, imin, icost, isupplier, idesc = inv_item
                stock = random.randint(imin * 2, imin * 5)
                conn.execute(
                    t_inv.insert().values(
                        restaurantId=resto_ids[ri],
                        name=iname,
                        description=idesc,
                        unit=iunit,
                        currentStock=stock,
                        minimumStock=imin,
                        unitPrice=icost,
                        supplier=isupplier,
                        createdAt=NOW,
                        updatedAt=NOW,
                    )
                )
                inv_id = conn.execute(
                    t_inv.select()
                    .with_only_columns(t_inv.c.id)
                    .where(t_inv.c.restaurantId == resto_ids[ri])
                    .where(t_inv.c.name == iname)
                ).scalar()
                all_inv_ids.append(inv_id)
        logger.info(f" Inventory seeded for {len(resto_ids)} restaurants")

        # ── Ingredient Links (DishInventoryLink) ────
        link_count = 0
        for ri in range(n_restos):
            # Fetch dishes and inventory for this restaurant
            restaurant_dishes = conn.execute(
                t_dish.select()
                .join(t_cat, t_dish.c.categoryId == t_cat.c.id)
                .join(t_menu, t_cat.c.menuId == t_menu.c.id)
                .where(t_menu.c.restaurantId == resto_ids[ri])
            ).fetchall()
            restaurant_inv = conn.execute(
                t_inv.select().where(t_inv.c.restaurantId == resto_ids[ri])
            ).fetchall()
            inv_by_name = {row.name: row.id for row in restaurant_inv}

            for dish_row in restaurant_dishes:
                if dish_row.name in dish_to_inv_map:
                    for ing_name in dish_to_inv_map[dish_row.name]:
                        if ing_name in inv_by_name:
                            quantity = round(random.uniform(0.05, 0.5), 2)
                            conn.execute(
                                t_ing_link.insert().values(
                                    dishId=dish_row.id,
                                    InventoryId=inv_by_name[ing_name],
                                    quantity=quantity,
                                )
                            )
                            link_count += 1
        logger.info(f" {link_count} ingredient links seeded")

        # ── Promotions ────
        promo_count = 0
        for ri in range(n_restos):
            for p in PROMOTIONS:
                title, ptype, dtype, dval, min_amt, days, pdesc = p
                conn.execute(
                    t_promo.insert().values(
                        restaurantId=resto_ids[ri],
                        title=title,
                        description=pdesc,
                        type=ptype,
                        discountType=dtype,
                        discountValue=dval,
                        minOrderAmount=min_amt if min_amt > 0 else None,
                        startDate=NOW,
                        endDate=NOW + timedelta(days=days),
                        isActive=True,
                        currentUses=0,
                        createdAt=NOW,
                        updatedAt=NOW,
                    )
                )
                promo_count += 1
        logger.info(f" {promo_count} promotions seeded")

        # ── Loyalty Cards ────
        for cu in client_users:
            points = random.randint(50, 500)
            conn.execute(
                t_loyalty.insert().values(
                    userId=cu.id,
                    points=points,
                    createdAt=NOW,
                    updatedAt=NOW,
                )
            )
        logger.info(f" {len(client_users)} loyalty cards seeded")

        # ── Reservations ────
        res_count = 0
        for ci in range(min(n_restos, len(client_users))):
            ri = ci % n_restos
            table_result = conn.execute(
                t_table.select().where(t_table.c.restaurantId == resto_ids[ri]).limit(1)
            ).fetchone()
            if table_result:
                start = NOW + timedelta(days=1, hours=19)
                end = start + timedelta(hours=2)
                conn.execute(
                    t_reservation.insert().values(
                        userId=client_users[ci].id,
                        restaurantId=resto_ids[ri],
                        tableId=table_result.id,
                        reservationStart=start,
                        reservationEnd=end,
                        status="CONFIRMED",
                        createdAt=NOW,
                        updatedAt=NOW,
                    )
                )
                res_count += 1
        logger.info(f" {res_count} reservations seeded")

        # ── Orders + Order Items + Reviews + Loyalty Transactions ────
        order_count = 0
        review_count = 0
        completed_orders = []

        for days_ago in [0, 1, 2, 3, 5, 7, 10, 14, 21, 28]:
            for slot in range(6):
                ci = (days_ago + slot) % len(client_users)
                ri = (days_ago + slot) % n_restos
                cu = client_users[ci]

                # Pick a random table for this restaurant
                tables_in_resto = conn.execute(
                    t_table.select().where(t_table.c.restaurantId == resto_ids[ri])
                ).fetchall()
                if not tables_in_resto:
                    continue
                table_row = random.choice(tables_in_resto)

                # Pick random dishes from this restaurant's menu
                restaurant_dishes = conn.execute(
                    t_dish.select()
                    .join(t_cat, t_dish.c.categoryId == t_cat.c.id)
                    .join(t_menu, t_cat.c.menuId == t_menu.c.id)
                    .where(t_menu.c.restaurantId == resto_ids[ri])
                ).fetchall()
                if not restaurant_dishes:
                    continue
                num_items = random.randint(1, 4)
                selected = random.sample(
                    restaurant_dishes, min(num_items, len(restaurant_dishes))
                )
                subtotal = sum(d.price for d in selected)
                total = round(subtotal + random.uniform(0, 5), 2)

                timestamp = past_time(
                    days_ago, random.randint(10, 22), random.randint(0, 59)
                )
                confirmed_at = timestamp + timedelta(minutes=random.randint(2, 10))
                prepared_at = confirmed_at + timedelta(minutes=random.randint(8, 25))
                ready_at = prepared_at + timedelta(minutes=random.randint(2, 8))
                completed_at = ready_at + timedelta(minutes=random.randint(1, 5))

                status_val = (
                    "COMPLETED"
                    if days_ago > 0
                    else random.choice(["CONFIRMED", "PREPARING", "READY", "COMPLETED"])
                )
                pay_status = (
                    "PAID"
                    if status_val == "COMPLETED"
                    else random.choice(["PENDING", "PAID"])
                )
                order_type = random.choice(["DINE_IN", "TAKEAWAY", "DELIVERY"])
                order_num = f"ORD-{1000 + order_count}"

                delivery_est = confirmed_at + timedelta(minutes=random.randint(20, 50))

                conn.execute(
                    t_order.insert().values(
                        orderNumber=order_num,
                        userId=cu.id,
                        restaurantId=resto_ids[ri],
                        tableId=table_row.id,
                        type=order_type,
                        status=status_val,
                        subtotal=round(subtotal, 2),
                        totalAmount=total,
                        deliveryFee=round(random.uniform(0, 3), 2),
                        estimatedDeliveryTime=delivery_est,
                        paymentStatus=pay_status,
                        orderTime=timestamp,
                        confirmedAt=confirmed_at,
                        preparedAt=prepared_at
                        if status_val in ("COMPLETED", "READY", "PREPARING")
                        else None,
                        readyAt=ready_at
                        if status_val in ("COMPLETED", "READY")
                        else None,
                        completedAt=completed_at if status_val == "COMPLETED" else None,
                        createdAt=timestamp,
                        updatedAt=NOW,
                    )
                )
                order_id = conn.execute(
                    t_order.select()
                    .with_only_columns(t_order.c.id)
                    .where(t_order.c.orderNumber == order_num)
                ).scalar()

                if status_val == "COMPLETED":
                    completed_orders.append({
                        "userId": cu.id,
                        "restaurantId": resto_ids[ri],
                        "totalAmount": total,
                        "orderId": order_id,
                        "orderNumber": order_num,
                    })

                for dish_row in selected:
                    qty = random.randint(1, 3)
                    conn.execute(
                        t_oi.insert().values(
                            orderId=order_id,
                            dishId=dish_row.id,
                            quantity=qty,
                            unitPrice=dish_row.price,
                            totalPrice=round(dish_row.price * qty, 2),
                        )
                    )
                order_count += 1

                # Review for completed orders
                if status_val == "COMPLETED":
                    chosen = random.choice(selected)
                    conn.execute(
                        t_review.insert().values(
                            userId=cu.id,
                            restaurantId=resto_ids[ri],
                            dishId=chosen.id,
                            rating=random.randint(4, 5),
                            comment=random.choice(
                                [
                                    "Excellent ! Un voyage culinaire en Algérie.",
                                    "Plats traditionnels délicieux, service impeccable.",
                                    "Les saveurs authentiques de l'Algérie à chaque bouchée.",
                                    "Meilleur couscous de la ville !",
                                    "Un vrai régal, je recommande vivement.",
                                    "Cuisine algérienne de qualité supérieure.",
                                    "Rapport qualité-prix excellent, je reviendrai.",
                                    "Les pâtisseries sont divines, comme chez ma grand-mère.",
                                ]
                            ),
                            isVerified=True,
                            createdAt=completed_at,
                            updatedAt=completed_at,
                        )
                    )
                    review_count += 1

        logger.info(f" {order_count} orders and {review_count} reviews seeded")

        # ── Loyalty Transactions ────
        txn_count = 0
        completed_user_ids = set()
        for o in completed_orders:
            completed_user_ids.add(o["userId"])
        loyalty_cards_db = conn.execute(
            t_loyalty.select().with_only_columns(t_loyalty.c.id, t_loyalty.c.userId)
        ).fetchall()
        for order_row in completed_orders:
            lc = next((lc for lc in loyalty_cards_db if lc.userId == order_row["userId"]), None)
            if lc:
                points_earned = int(order_row["totalAmount"])
                conn.execute(
                    t_txn.insert().values(
                        loyaltyCardId=lc.id,
                        restaurantId=order_row["restaurantId"],
                        points=points_earned,
                        type="EARNED",
                        description=f"Points gagnés sur la commande {order_row['orderNumber']}",
                        createdAt=NOW,
                    )
                )
                txn_count += 1
        logger.info(f" {txn_count} loyalty transactions seeded")

    engine.dispose()
    logger.info("PostgreSQL seeding complete ✅")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SQLITE SEED  (AI Inventory DB)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def seed_sqlite():
    logger.info("Seeding AI SQLite database at %s ...", AI_SQLITE_PATH)

    if not os.path.exists(AI_SQLITE_PATH):
        logger.warning(
            "SQLite file not found at %s. The AI service may not have started yet.",
            AI_SQLITE_PATH,
        )
        return

    conn = sqlite3.connect(AI_SQLITE_PATH)
    cursor = conn.cursor()

    # Idempotent: clear and re-seed
    cursor.execute("SELECT COUNT(*) FROM food_items")
    count = cursor.fetchone()[0]
    if count > 0:
        logger.info("Clearing existing AI data (%d food items)...", count)
        cursor.execute("DELETE FROM food_items")
    logger.info("Inserting Algerian food items...")

    ALGERIAN_FOOD_ITEMS = [
        # (name, category, unit, description)
        (
            "Semoule",
            "Céréales",
            "kg",
            "Semoule de blé dur pour couscous et pâtisseries",
        ),
        ("Couscous", "Céréales", "kg", "Couscous précuit traditionnel"),
        ("Viande d'Agneau", "Viande", "kg", "Viande d'agneau locale"),
        ("Viande de Bœuf", "Viande", "kg", "Viande de bœuf halal"),
        ("Poulet Fermier", "Viande", "kg", "Poulet fermier élevé au grain"),
        ("Merguez", "Viande", "kg", "Saucisses épicées algériennes"),
        ("Poisson Merlan", "Poisson", "kg", "Merlan frais de Méditerranée"),
        ("Pois Chiches", "Légumineuses", "kg", "Pois chiches secs"),
        ("Lentilles", "Légumineuses", "kg", "Lentilles brunes"),
        ("Fèves", "Légumineuses", "kg", "Fèves décortiquées"),
        ("Tomates", "Légumes", "kg", "Tomates fraîches du marché"),
        ("Oignons", "Légumes", "kg", "Oignons jaunes"),
        ("Ail", "Légumes", "kg", "Ail frais du pays"),
        ("Poivrons Verts", "Légumes", "kg", "Poivrons verts"),
        ("Courgettes", "Légumes", "kg", "Courgettes fraîches"),
        ("Carottes", "Légumes", "kg", "Carottes fraîches"),
        ("Pommes de Terre", "Légumes", "kg", "Pommes de terre locales"),
        ("Navets", "Légumes", "kg", "Navets frais"),
        ("Huile d'Olive", "Épices & Huiles", "litre", "Huile d'olive extra vierge"),
        ("Beurre", "Produits Laitiers", "kg", "Beurre frais"),
        ("Lait", "Produits Laitiers", "litre", "Lait entier frais"),
        ("Œufs", "Produits Laitiers", "unité", "Œufs fermiers"),
        ("Fromage", "Produits Laitiers", "kg", "Fromage frais local"),
        ("Olives Vertes", "Conserves", "kg", "Olives vertes confites"),
        ("Citrons Confits", "Conserves", "kg", "Citrons confits au sel"),
        ("Dattes Deglet Nour", "Fruits Secs", "kg", "Dattes Deglet Nour de Tolga"),
        ("Miel", "Sucreries", "kg", "Miel du Djurdjura"),
        ("Amandes", "Fruits Secs", "kg", "Amandes mondées"),
        ("Noix", "Fruits Secs", "kg", "Noix de Kabylie"),
        ("Menthe", "Herbes", "botte", "Menthe fraîche"),
        ("Coriandre", "Herbes", "botte", "Coriandre fraîche"),
        ("Persil", "Herbes", "botte", "Persil plat frais"),
        ("Cumin", "Épices", "kg", "Cumin moulu"),
        ("Paprika", "Épices", "kg", "Paprika doux"),
        ("Safran", "Épices", "g", "Safran pur"),
        ("Ras El Hanout", "Épices", "kg", "Mélange d'épices algérien"),
        ("Cannelle", "Épices", "kg", "Bâtons de cannelle"),
        ("Harissa", "Condiments", "kg", "Pâte de piment algérienne"),
        ("Eau de Fleur d'Oranger", "Arômes", "litre", "Eau de fleur d'oranger"),
        ("Vermicelle", "Pâtes", "kg", "Vermicelle fine"),
        ("Feuilles de Brick", "Pâtes", "paquet", "Feuilles de brick"),
        ("Raisins Secs", "Fruits Secs", "kg", "Raisins secs du Sud"),
        ("Pâte de Tomate", "Conserves", "kg", "Double concentré de tomate"),
        (
            "Khlii (Viande Séchée)",
            "Viande",
            "kg",
            "Viande d'agneau séchée traditionnelle",
        ),
        ("Pruneaux", "Fruits Secs", "kg", "Pruneaux d'Afrique du Nord"),
        ("Semoule Fine", "Céréales", "kg", "Semoule fine pour pâtisseries"),
        ("Semoule Grosse", "Céréales", "kg", "Grosse semoule pour couscous"),
        ("Farine", "Céréales", "kg", "Farine de blé"),
        ("Pignons de Pin", "Fruits Secs", "kg", "Pignons de pin pour thé"),
        ("Thé Vert", "Boissons", "kg", "Thé vert pour thé à la menthe"),
    ]

    from datetime import datetime as dt_mod

    now_ts = dt_mod.now().isoformat()

    for name, cat, unit, desc in ALGERIAN_FOOD_ITEMS:
        cursor.execute(
            "INSERT INTO food_items (name, category, unit, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, cat, unit, desc, now_ts, now_ts),
        )

    conn.commit()
    conn.close()
    logger.info(
        f"AI SQLite seeded with {len(ALGERIAN_FOOD_ITEMS)} Algerian food items ✅"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def main():
    logger.info("=" * 50)
    logger.info("Mayda Seed — Initializing databases")
    logger.info("=" * 50)

    seed_postgres()
    seed_sqlite()

    logger.info("=" * 50)
    logger.info("✅ Seeding complete! Databases are ready.")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()