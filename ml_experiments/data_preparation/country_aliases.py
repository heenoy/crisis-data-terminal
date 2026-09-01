"""Central country-name aliases for reporting only.

HDRO merging uses exact ISO3 + year and does not rely on these aliases.
"""

COUNTRY_ALIASES = {
    "bolivia (plurinational state of)": "Bolivia",
    "congo (democratic republic of the)": "Democratic Republic of the Congo",
    "korea (republic of)": "Republic of Korea",
    "moldova (republic of)": "Republic of Moldova",
    "tanzania (united republic of)": "United Republic of Tanzania",
    "venezuela (bolivarian republic of)": "Venezuela",
}

# Explicit classification notes for well-formed EM-DAT codes absent from HDRO.
# The EM-DAT code universe is still read from the workbook; these are not used
# as an input country list and never redirect HDI values to another country.
HISTORICAL_ISO3_CODES = {
    "ANT": "Netherlands Antilles, dissolved in 2010",
    "SCG": "Serbia and Montenegro, dissolved in 2006",
}

EMDAT_NONSTANDARD_SPECIAL_CODES = {
    "AZO": "EM-DAT special code for the Azores Islands",
    "SPI": "EM-DAT special code for the Canary Islands",
}
