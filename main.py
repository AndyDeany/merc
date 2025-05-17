import re
from time import sleep, time

import requests
from bs4 import BeautifulSoup


class Listing:

    MERC_RUN_REGEX = re.compile(r"(^|[\d. \n])\d ?m($|i($|[^n])|[^a-zA-Z0-9])", re.IGNORECASE)
    ALLOWED_DUTIES = (
        "Recollection (Extreme)",
        "AAC Cruiserweight M1 (Savage)",
        "AAC Cruiserweight M2 (Savage)",
        "AAC Cruiserweight M3 (Savage)",
        "AAC Cruiserweight M4 (Savage)",
    )

    def __init__(self, html):
        self.duty = html.find("div", class_="duty").text
        self.description = html.find("div", class_="description").text.replace("\r", "\n")
        self.creator = html.find("div", class_="item creator").find("span", class_="text").text
        self.creator = self.creator.split("@")[0].strip()
        self.updated = html.find("div", class_="updated").find("span", class_="text").text
        party_div = html.find("div", class_="party")
        self.slots = [Slot(slot) for slot in party_div.find_all("div", class_="slot")]

    @property
    def is_merc_run(self):
        return bool(self.MERC_RUN_REGEX.search(self.description))

    @property
    def is_allowed_duty(self):
        return self.duty in self.ALLOWED_DUTIES

    @property
    def is_valid(self):
        return self.is_merc_run and self.is_allowed_duty

    @property
    def updated_as_discord_timestamp(self):
        updated_timestamp = int(time()) - self.seconds_passed_since_updated
        return f"<t:{updated_timestamp}:R>"

    TIME_PASSED_REGEX = re.compile(r"(\d+) (second|minute)s? ago")

    @property
    def seconds_passed_since_updated(self):
        if self.updated == "now":
            return 0

        time_passed = self.TIME_PASSED_REGEX.match(self.updated)
        value = int(time_passed[1])
        unit = time_passed[2]

        if unit == "second":
            return value
        if unit == "minute":
            return 60*value

        print(f"Couldn't parse time passed {self.updated}")
        return 31_536_000   # Seconds in a year for errors

    def __eq__(self, other):
        return (self.duty == other.duty and
                self.description == other.description and
                self.creator == other.creator)

    def __repr__(self):
        string = ""
        string += f"**{self.duty} | {self.creator} | Updated {self.updated_as_discord_timestamp}"
        string += f"{self.description}\n"
        string += " ".join(str(slot) for slot in self.slots if not slot.is_filled)
        return string


class Slot:

    CLASS_FILLED = "filled"
    CLASS_TANK = "tank"
    CLASS_HEALER = "healer"
    CLASS_DPS = "dps"

    def __init__(self, html):
        self.classes = html.get("class", [])
        self.is_filled = self.CLASS_FILLED in self.classes
        self.jobs = html.get("title").split(" ")

    def __repr__(self):
        if self.is_filled:
            return ":x:"

        roles = []

        if self.CLASS_TANK in self.classes:
            roles.append(":blue_heart:")
        if self.CLASS_HEALER in self.classes:
            roles.append(":green_heart:")
        if self.CLASS_DPS in self.classes:
            roles.append(":heart:")

        return "/".join(roles)


class MercNotifier:

    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1372683969916833792/kM2WEgFqly7fdmF-J8Gv-scibT5zqWT5fJnNwqs10bk7olbNUA9UUPvUv5iu4wdHPBT7"
    DISCORD_WEBHOOK_URL_DEV = "https://discord.com/api/webhooks/1372583493334470738/Fx2RE-XwqehlXzY9B9SOyFkBFoLssqTXyzucNWIgTmX3yioWwgmIigKyatgTr8iQ_FAq"

    def __init__(self):
        self.notified_listings = []
        self.first_run = True

    def run(self):
        while True:
            self.check_listings()
            sleep(30)

    @staticmethod
    def get_listings():
        soup = BeautifulSoup(requests.get("https://xivpf.com/listings").text, "html.parser")
        listings = soup.select("div#listings div.listing[data-centre='Light']")
        return [Listing(listing) for listing in listings]

    def send_discord_notification(self, message):
        requests.post(self.DISCORD_WEBHOOK_URL, json={"content": message})

    def check_listings(self):
        for listing in self.get_listings():
            if listing.is_valid and listing not in self.notified_listings:
                if not self.first_run:  # Don't post on first run to avoid spam on restarting
                    self.send_discord_notification(str(listing))
                else:
                    print(str(listing))
                self.notified_listings.append(listing)
        self.first_run = False


if __name__ == "__main__":
    MercNotifier().run()
