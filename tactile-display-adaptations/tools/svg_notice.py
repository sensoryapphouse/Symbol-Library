"""Non-visible rights notice for SVG masters and generated exports."""
import xml.etree.ElementTree as ET
NOTICE = "Copyright Sensory App House Ltd, CC BY-NC 4.0."
LICENSE_URI = "https://creativecommons.org/licenses/by-nc/4.0/"
def ensure_notice(root):
    matches = [e for e in root if e.get("id") == "copyright-notice"]
    if len(matches) > 1:
        raise ValueError("Duplicate copyright notice")
    node = matches[0] if matches else ET.SubElement(root, "{http://www.w3.org/2000/svg}metadata", {"id": "copyright-notice"})
    node.set("data-license", "CC-BY-NC-4.0")
    node.set("data-license-uri", LICENSE_URI)
    node.text = NOTICE
