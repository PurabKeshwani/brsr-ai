"""
Sector Classification — NIC-2008 Division-Level Grouping

NIC-2008 (National Industrial Classification) structure, confirmed via
official sources (Ministry of Statistics and Programme Implementation):
Section (1 letter) -> Division (2-digit) -> Group (3-digit) ->
Class (4-digit) -> Sub-class (5-digit).

This project's ingested NIC codes vary in length (3 to 6 digits observed
across real filings — some filers pad or use non-standard extensions),
so sector grouping uses the first 2 digits (the Division level) as the
consistent bucket, regardless of the full code's length. This is the
standard "broad sector" grouping in NIC-based analysis.

Division-name mapping below covers divisions actually observed in this
project's ingested data (not the full 88-division NIC table) — verified
against real NIC codes seen in the database, not assumed.
"""
from __future__ import annotations

# Division (2-digit prefix) -> broad sector name. Sourced from official
# NIC-2008 division descriptions (MoSPI), limited to divisions actually
# observed in this project's ingested filings.
DIVISION_TO_SECTOR: dict[str, str] = {
    "01": "Agriculture, Forestry and Fishing",
    "05": "Mining and Quarrying", "06": "Mining and Quarrying", "07": "Mining and Quarrying",
    "08": "Mining and Quarrying", "09": "Mining and Quarrying",
    "10": "Food Products Manufacturing", "11": "Beverages Manufacturing", "12": "Tobacco Products",
    "13": "Textiles", "14": "Wearing Apparel", "15": "Leather Products",
    "16": "Wood Products", "17": "Paper Products", "18": "Printing",
    "19": "Coke and Refined Petroleum", "20": "Chemicals Manufacturing", "21": "Pharmaceuticals",
    "22": "Rubber and Plastics", "23": "Non-Metallic Mineral Products",
    "24": "Basic Metals", "25": "Fabricated Metal Products",
    "26": "Computer, Electronic and Optical Products", "27": "Electrical Equipment",
    "28": "Machinery and Equipment", "29": "Motor Vehicles", "30": "Other Transport Equipment",
    "31": "Furniture", "32": "Other Manufacturing", "33": "Repair and Installation of Machinery",
    "35": "Electricity, Gas, Steam and AC Supply",
    "36": "Water Supply and Waste Management", "37": "Water Supply and Waste Management",
    "38": "Water Supply and Waste Management", "39": "Water Supply and Waste Management",
    "41": "Construction", "42": "Civil Engineering", "43": "Specialized Construction",
    "45": "Wholesale/Retail Trade - Motor Vehicles", "46": "Wholesale Trade", "47": "Retail Trade",
    "49": "Land Transport", "50": "Water Transport", "51": "Air Transport",
    "52": "Warehousing and Transport Support", "53": "Postal and Courier",
    "55": "Accommodation", "56": "Food and Beverage Service",
    "58": "Publishing Activities", "59": "Motion Picture and Sound Production",
    "60": "Broadcasting", "61": "Telecommunications",
    "62": "Computer Programming and IT Services", "63": "Information Service Activities",
    "64": "Financial Services (excl. Insurance)", "65": "Insurance and Pension Funding",
    "66": "Auxiliary Financial Services",
    "68": "Real Estate Activities",
    "69": "Legal and Accounting Activities", "70": "Head Office and Management Consultancy",
    "71": "Architecture and Engineering", "72": "Scientific R&D", "73": "Advertising and Market Research",
    "74": "Other Professional/Technical Activities", "75": "Veterinary Activities",
    "77": "Rental and Leasing", "78": "Employment Activities",
    "79": "Travel Agency Activities", "80": "Security and Investigation",
    "81": "Building/Landscape Services", "82": "Office Administrative Support",
    "84": "Public Administration", "85": "Education",
    "86": "Human Health Activities", "87": "Residential Care", "88": "Social Work Activities",
    "90": "Creative and Arts Activities", "91": "Libraries and Museums",
    "92": "Gambling and Betting", "93": "Sports and Recreation",
    "94": "Membership Organizations", "95": "Repair of Personal Goods",
    "96": "Other Personal Service Activities",
}

UNKNOWN_SECTOR_LABEL = "Unclassified"


def get_sector_from_nic_code(nic_code: str | None) -> str:
    """Maps a raw NIC code (any length 3-6 digits, as observed in real
    filings) to a broad sector name via its 2-digit Division prefix."""
    if not nic_code or not nic_code.strip():
        return UNKNOWN_SECTOR_LABEL
    cleaned = nic_code.strip()
    if len(cleaned) < 2 or not cleaned[:2].isdigit():
        return UNKNOWN_SECTOR_LABEL
    division = cleaned[:2]
    return DIVISION_TO_SECTOR.get(division, f"Other (Division {division})")