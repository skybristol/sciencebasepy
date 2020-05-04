"""This Python module provides some basic services for interacting with ScienceBase."""
from __future__ import print_function

import requests
import extruct
from w3lib.html import get_base_url
from bs4 import BeautifulSoup
from gis_metadata.metadata_parser import get_metadata_parser
from xml.etree import ElementTree as ET
from datetime import datetime

from sciencebasepy.SbSession import SbSession


class Weblinks:
    def __init__(self):
        self.description = "Module for working with ScienceBase web links"
        self.sb = SbSession()

    def process_web_links(self, fields="webLinks", item_id=None, item=None, link_type=None, link_title=None):
        """Processes a ScienceBase Item to return enhanced information on each web link

        :param fields: Specify the item fields to include; defaults to just the webLinks
        :param item_id: ScienceBase Item UUID identifier
        :param item: Full ScienceBase Item
        :param link_type: Type classification term to filter links
        :param link_title: Title text to filter links; matches exact text
        :return: annotated item containing structured information scraped for each link
        """
        if item is None and item_id is None:
            raise Exception("Must provide either a ScienceBase Item or an item_id")

        if item is None and item_id is not None:
            item = self.sb.get_item(item_id, params={"fields": fields})

            if item is None:
                raise Exception("Item could not be found by the supplied item_id")

        if "webLinks" not in item.keys():
            return item

        annotated_links = list()

        for link in item["webLinks"]:
            if link_type is not None and link["type"] == link_type:
                annotated_links.append(link)
                item["webLinks"].next()
                continue

            if link_title is not None and link["title"] == link_title:
                annotated_links.append(link)
                item["webLinks"].next()
                continue

            annotated_links.append(self.link_meta(link))

        del item["webLinks"]
        item["webLinks"] = annotated_links

        return item

    def get_weblink_response(self, web_link):
        """Retrieves a basic response for a ScienceBase web link object and returns the response with decoration.

        :param web_link: ScienceBase Item web link object
        :return: Annotated web link object and the requests response
        """
        annotated_web_link = web_link
        annotated_web_link["annotation"] = {
            "link_check_date": datetime.utcnow().isoformat(),
            "content_type": "UNKNOWN"
        }

        try:
            response = requests.get(web_link["uri"],
                                    headers={"Accept": "application/json,application/xhtml+xml,text/html"})
            response.raise_for_status()
        except Exception as err:
            annotated_web_link["annotation"]["content_type"] = "ERROR"
            annotated_web_link["annotation"]["error_message"] = err
            return annotated_web_link, None

        annotated_web_link["annotation"]["status_code"] = response.status_code
        annotated_web_link["annotation"]["headers"] = response.headers
        annotated_web_link["annotation"]["encoding"] = response.encoding

        if response.status_code != 200:
            return annotated_web_link, response

        if bool(BeautifulSoup(response.text, "html.parser").find()):
            try:
                x = ET.fromstring(response.text)
                annotated_web_link["annotation"]["content_type"] = "xml"
            except Exception as e:
                annotated_web_link["annotation"]["content_type"] = "html"
        else:
            try:
                x = response.json()
                annotated_web_link["annotation"]["content_type"] = "json"
            except Exception as e:
                pass

        return annotated_web_link, response

    def meta_scraper(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        meta_content = dict()

        if soup.title is not None:
            meta_content["title"] = soup.title.string

        for meta in soup.findAll("meta"):
            metaname = meta.get('name', '')
            try:
                metacontent = meta["content"].strip()
            except:
                metacontent = None
            if isinstance(metaname, str) and isinstance(metacontent, str) and len(metacontent) > 0:
                meta_content[metaname] = metacontent

        return meta_content

    def summarize_xml_meta(self, xml_content):
        meta = get_metadata_parser(xml_content)

        meta_summary = dict()
        meta_summary["title"] = meta.title
        meta_summary["abstract"] = meta.abstract
        meta_summary["place_keywords"] = meta.place_keywords
        meta_summary["thematic_keywords"] = meta.thematic_keywords
        meta_summary["attributes"] = meta.attributes
        meta_summary["bounding_box"] = meta.bounding_box
        meta_summary["contacts"] = meta.contacts
        meta_summary["dates"] = meta.dates
        meta_summary["digital_forms"] = meta.digital_forms
        meta_summary["larger_works"] = meta.larger_works
        meta_summary["process_steps"] = meta.process_steps
        meta_summary["raster_info"] = meta.raster_info

        return meta_summary

    def link_meta(self, web_link):
        """Takes a ScienceBase Item's web link object and attempts to scrape as much metadata as possible about it.

        :param web_link: ScienceBase Item web link object
        :return: Web link object with annotations and structured metadata
        """
        annotated_link, r = self.get_weblink_response(web_link)

        if annotated_link["annotation"]["content_type"] == "html":
            annotated_link["annotation"]["meta_content"] = self.meta_scraper(r.text)

            try:
                annotated_link["annotation"]["structured_data"] = extruct.extract(r.text, base_url=get_base_url(r.text, r.url))
            except Exception as e:
                annotated_link["annotation"]["structured_data"] = None

        if annotated_link["annotation"]["content_type"] == "xml":
            annotated_link["annotation"]["xml_meta_summary"] = self.summarize_xml_meta(r.text)

        if annotated_link["annotation"]["content_type"] == "json":
            annotated_link["annotation"]["json_content"] = r.json()

        return annotated_link


