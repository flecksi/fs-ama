from pathlib import Path

from urllib.request import urlretrieve
import scrapy
import scrapy.responsetypes
from scrapy.selector import Selector
import datetime
import re


class FSEpisodeSpider(scrapy.Spider):
    name = "fs_episodes"
    start_urls = [
        "https://freakshow.fm/archiv",
    ]

    def parse(self, response):
        for episode in response.css("ul.archive li.archive__element"):
            guest_names = [
                guest.css("figcaption.show__guest__name::text").get()
                for guest in episode.css("div.show__guests figure.show__guest")
            ]

            chapters = episode.css("ol li::text").getall()

            duration_string = re.sub(
                r"\s+",
                " ",
                episode.css("span.show__meta-data--duration::text")
                .get()
                .replace("\t", " ")
                .replace("\n", " ")
                .strip(),
            )

            dur_parts = duration_string.split(" ")
            duration_minutes = None
            if len(dur_parts) == 2:
                if "Stund" in dur_parts[1]:
                    duration_minutes = int(dur_parts[0]) * 60
                elif "Minut" in dur_parts[1]:
                    duration_minutes = int(dur_parts[0])
            elif len(dur_parts) == 4:
                duration_minutes = int(dur_parts[0]) * 60 + int(dur_parts[2])

            episode_dict = {
                "title": episode.css("a.show__title__link::text").get(),
                "url": episode.css("a.show__title__link::attr(href)").get(),
                "date": datetime.datetime.strptime(
                    episode.css("span.show__meta-data--date::text").get().strip(),
                    "%d.%m.%Y",
                ).strftime("%Y-%m-%d"),
                # "duration_string": duration_string,
                "duration_minutes": duration_minutes,
                "descr_short": episode.css("p.show__description::text").get(),
                "chapters": chapters,
                "n_chapters": len(chapters),
                "guests": guest_names,
                "n_guests": len(guest_names),
            }
            for guest in guest_names:
                episode_dict[f"guest:{guest}"] = True

            download_webvtt = getattr(self, "dlwebvtt", False)
            if download_webvtt:
                yield scrapy.Request(
                    episode.css("a.show__title__link::attr(href)").get(),
                    callback=self.parse_single_episode,
                    meta={"episode": episode_dict},
                )
            else:
                yield episode_dict

    def parse_single_episode(self, response):
        episode_dict = response.meta["episode"]

        webvtt_available = False
        webvtt_link = None
        for link in response.css("p>a"):
            if link.css("a::text").get() == "WEBVTT":
                webvtt_available = True
                webvtt_link = link.css("a::attr(href)").get()

                # download the webvtt_link
                local_webvtt_path = Path(
                    f"episode_transcripts/{episode_dict['title'].split()[0]}.vtt"
                )
                local_webvtt_path.parent.mkdir(parents=True, exist_ok=True)
                urlretrieve(url=webvtt_link, filename=local_webvtt_path)

                break

        descr_long = response.css("div.entry-content p:nth-child(2)::text").get()
        if descr_long is None:
            descr_long = response.css("div.entry-content p:nth-child(3)::text").get()
        episode_dict["descr_long"] = descr_long
        episode_dict["webvtt_available"] = webvtt_available
        episode_dict["webvtt_link"] = webvtt_link
        yield episode_dict
