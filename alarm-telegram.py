# -*- coding: utf-8 -*-
"""
Alarm-Telegram_24.12.3

Created on 07.12.2024

@author: Odinxii
"""

import imaplib
import os
import sys
import time
import email
import logging
import requests
import xml.etree.ElementTree as ET
from prettytable import PrettyTable, PLAIN_COLUMNS
from concurrent.futures import ThreadPoolExecutor

# Konfiguriere das Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TelegramLogHandler(logging.Handler):
    def __init__(self, chat_id):
        super().__init__(logging.WARNING)  # Nur Logs ab WARNING
        self.chat_id = chat_id

    def emit(self, record):
        log_entry = self.format(record)  # Formatierte Log-Nachricht
        send_to_telegram(log_entry, self.chat_id)

def send_to_telegram(message, telegram_chatid):
    """
    Sendet eine Nachricht an Telegram.
    """
    if not APIToken or not telegram_chatid:
        logging.error("Chat ID or token is not configured. Message not sent.")
        return

    APIURL = f'https://api.telegram.org/bot{APIToken}/sendMessage'

    for z in range(10):
        try:
            response = requests.post(APIURL, json={'chat_id': telegram_chatid, 'text': message}, timeout = 5)
            data = response.json()
        
            # Prüfen, ob die Nachricht erfolgreich war
            if response.status_code == 200 and data.get("ok"):
                logging.info(f"Message successfully delivered to Telegram: {telegram_chatid}")
                return None
            else:
                error_message = data.get("description", "Unbekannter Fehler")
                logging.error(f"Error while sending the message: {error_message}")
                return None
        except requests.RequestException as e:
            logging.warning(f'Send Message Retry ... {z + 1}/10')
            if z == 9:
                logging.error(f"Telegram Chat Timeout\nChatID: {telegram_chatid}\n Error: {e}")
                
                
    return None

def get_telegram_chatid_for_wache(wache, typ):
    """
    Gibt das Gotify-Token für eine spezifische Wache zurück.
    """
    if wache not in wachen_list:
        return None
    
    if typ == "telegram_chatid":
        return alarmierungs_daten[wache]["telegram_chatid"]
    elif typ == "bot_chatid":
        return alarmierungs_daten[wache]["bot_chatid"]
    else:
        logging.warning(f"No Telegram Chat ID or Bot ID found for the station '{wache}'.")
        return None


def reconnect_imap():
    global imap
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            # close the connection and logout if not already in LOGOUT state
            if imap and imap.state != 'LOGOUT':
                imap.logout()
                logging.info("IMAP connection logged out")
                time.sleep(retry_delay)  # Wait before attempting to reconnect

            # initialise IMAP
            imap = imaplib.IMAP4_SSL(imap_server, imap_port)
            imap.login(username, password)
            logging.info("IMAP connection restored")
            return imap
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries} - Error while restoring the IMAP connection: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)  # Wait before retrying
            else:
                logging.error("Max retries reached. Could not restore IMAP connection.")
                return None

def send_emergency_alert(wache, message, message_for_bot):
    """
    Senden einer Alarmmeldung an die entsprechende Telegram-Gruppe.
    """
    full_message = f"Einsatz für: {wache}\n\n{message}"
    chatid = get_telegram_chatid_for_wache(wache, "telegram_chatid")
    bot_chatid = get_telegram_chatid_for_wache(wache, "bot_chatid")

    logging.info(f"Emergency for: {wache}")
    send_to_telegram(message_for_bot, bot_chatid)
    send_to_telegram(full_message, chatid)
    
    return None

"""
def get_matching_wachen(file):
    # Path to XML
    tree = ET.parse(file)
    root = tree.getroot()
    
    # Sammle alle relevanten Werte aus der XML
    xml_values = {column.get('value', '') for column in root.findall(".//Column")}
    
    # Finde Übereinstimmungen
    matching_wachen = [wache for wache in wachen_list if wache in xml_values]

    if matching_wachen:
        message, message_for_bot = get_table(file, root)
        for wache in matching_wachen:
            send_emergency_alert(wache, message, message_for_bot)

    else:
        logging.info("No emergency for observed Teams")
    return ()
"""  

def get_matching_wachen(file):
    """
    Searches for matching 'Wachen' in the XML file based on their exact match or substring presence.
    """
    # Path to XML
    tree = ET.parse(file)
    root = tree.getroot()

    # Collect all relevant values from the XML
    xml_values = {column.get('value', '').lower() for column in root.findall(".//Column")}
    
    # Find matches based on full or partial match
    matching_wachen = [
        wache for wache in wachen_list
        if any(wache.lower() in xml_value for xml_value in xml_values)
    ]

    if matching_wachen:
        message, message_for_bot = get_table(file, root)
        for wache in matching_wachen:
            send_emergency_alert(wache, message, message_for_bot)
    else:
        logging.info("No emergency for observed Teams")
    return ()


def get_table(file, root):
    # list relevant Column Values if EM searched is in XML
    Meldungsliste = [""] * 25
    Header = ['Einsatznummer', 'Datum', 'Meldender', 'NummerdesMeldenden', 
                'Meldeweg', 'Einsatzstichwort', 'Meldebild', 'Ort', 'Ortsteil', 
                'Strasse', 'Hausnummer', 'Objekt', 'Unterobjekt', 'Ortszusatz', 
                'Bem.Einsatzort', 'Bem.Einsatzanlass', 'Rueckrufnummer', 
                'RueckrufBemerkung', 'Gefahrenmeldeanlage', 'EinsatzplanInfo', 
                'Infotext', 'PLZ', 'Strassenabschnitt', ' ', ' ', ' ']
    Value = [""] * 25
    x = 0
    for Meldung in root.iter('Column'):
        # convert dict values to list 
        Meldung_value = list(Meldung.attrib.values())
        Meldungsliste[x] = Header[x] + Meldung_value[0]
        Value[x] = Meldung_value[0]
        x += 1
        if x > 24:
            break
    
    # read coordiantes for gooogle maps link
    latitude = Meldungsliste[23]
    longitude = Meldungsliste[24]
    google_maps = f'https://maps.google.com/maps?q={latitude},{longitude}'
    google_maps_link = google_maps.replace(" ", "") if latitude and longitude else ""
    osmand_maps = f'https://osmand.net/map?pin={latitude},{longitude}'
    osmand_maps_link = osmand_maps.replace(" ", "") if latitude and longitude else ""

    
    # get Columns for Prettytable
    message_Header = [Header[5], Header[6], Header[7], Header[8], Header[9], Header[10], Header[14], Header[15]]
    message_Value = [Value[5], Value[6], Value[7], Value[8], Value[9], Value[10], Value[14], Value[15]]
    Meldetabelle = PrettyTable()
    Meldetabelle.add_column(Header[1], message_Header)
    Meldetabelle.add_column(Value[1], message_Value)
    
    # style Table
    Meldetabelle.align = "l"
    Meldetabelle.set_style(PLAIN_COLUMNS)

    # get Columns for Prettytable for bots
    message_Value = Value[6:10]
    Meldetabelle_bots = PrettyTable()
    Meldetabelle_bots.add_column(Value[5], message_Value)

    # style Table
    Meldetabelle_bots.align = "l"
    Meldetabelle_bots.set_style(PLAIN_COLUMNS)
    
    message = (f'Einsatzalarm\n\n{Meldetabelle}\n\n{google_maps_link}\n{osmand_maps_link}')
    message_for_bot = (f'/tts \nEinsatzalarm\n\n{Meldetabelle_bots}')
    return (message, message_for_bot)

def browse_mails():
    # use imap.list() to see all mailboxes
    global imap
    try:
        imap = imap or reconnect_imap()  # ensure imap is connected
        if imap:
            imap.select("INBOX")
            (status, messages) = imap.search(None, '(UNSEEN NOT SUBJECT "Einsatzabschluss")')
            if status == 'OK':
                for i in messages[0].split():
                    typ, data = imap.fetch(i, "(RFC822)")
                    for response in data:
                        if isinstance(response, tuple):
                            # parse a bytes email into a message object
                            data = email.message_from_bytes(response[1])
                            for part in data.walk():
                                # extract content disposition of email
                                content_disposition = str(part.get("Content-Disposition"))
                                if "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    # mark message as seen
                                    imap.store(i,'-FLAGS','Seen')
                                    if filename:
                                        folder_name = "AlarmXML"
                                        if not os.path.isdir(folder_name):
                                            # make a folder for this email
                                            os.mkdir(folder_name)
                                        filepath = os.path.join(folder_name, filename)
                                        # download attachment and save it
                                        open(filepath, "wb").write(part.get_payload(decode=True))
                                        get_matching_wachen(filepath)
                                        os.remove(filepath)
            else:
                logging.warning("IMAP connection timeout")               
                reconnect_imap()
                time.sleep(10)
        else:
            logging.error("IMAP connection could not be established.")
            reconnect_imap()
            time.sleep(10)
    except Exception as e:
        logging.error(f"Error while browsing mails: {e}")
        reconnect_imap()
        time.sleep(10)
    return ()

def main():
    while True:
        browse_mails()
        time.sleep(1)
            
if __name__ == "__main__":
    try:    
        # from environment variables
        username = os.environ.get('EMAIL_USERNAME')
        password = os.environ.get('EMAIL_PASSWORD')
        imap_server = os.environ.get('IMAP_SERVER')
        imap_port = int(os.environ.get('IMAP_PORT', 993))
        wachen_list = os.environ.get('WACHEN','').split(',')
        APIToken = os.environ.get('APITOKEN')
        telegram_chatids = os.environ.get('TELEGRAM_CHATIDS','').split(',')  
        bot_chatids = os.environ.get('BOT_CHATIDS','').split(',')  

        alarmierungs_daten = {
            wachen_list: {"telegram_chatid": telegram_chatid, "bot_chatid": bot_chatid}
            for wachen_list, telegram_chatid, bot_chatid in zip(wachen_list, telegram_chatids, bot_chatids)
        }

        # connect to IMAP Server
        imap = imaplib.IMAP4_SSL(imap_server, imap_port)
        imap.login(username, password)
        logging.info("Connected to IMAP server")
        main()
    except Exception as e:
        logging.error(f"Error starting the script: {e}") 