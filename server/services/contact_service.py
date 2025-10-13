import json
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class ContactService:
    def __init__(self, contacts_file: str = "contacts.json"):
        """Initialize contact service with persistent storage"""
        self.contacts_file = contacts_file
        self.contacts = self._load_contacts()
    
    def _load_contacts(self) -> Dict[str, str]:
        """Load contacts from JSON file"""
        try:
            if os.path.exists(self.contacts_file):
                with open(self.contacts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading contacts: {e}")
            return {}
    
    def _save_contacts(self) -> None:
        """Save contacts to JSON file"""
        try:
            with open(self.contacts_file, 'w', encoding='utf-8') as f:
                json.dump(self.contacts, f, indent=2, ensure_ascii=False)
            logger.info(f"Contacts saved to {self.contacts_file}")
        except Exception as e:
            logger.error(f"Error saving contacts: {e}")
    
    def get_contact_name(self, phone_number: str) -> str:
        """Get contact name, return phone number if no custom name is set"""
        return self.contacts.get(phone_number, phone_number)
    
    def set_contact_name(self, phone_number: str, name: str) -> None:
        """Set contact name and save to file"""
        if name and name.strip():
            self.contacts[phone_number] = name.strip()
            self._save_contacts()
            logger.info(f"Contact {phone_number} renamed to '{name}'")
        else:
            logger.warning(f"Attempted to set empty name for {phone_number}")
    
    def remove_contact_name(self, phone_number: str) -> None:
        """Remove custom name for contact (will revert to phone number)"""
        if phone_number in self.contacts:
            del self.contacts[phone_number]
            self._save_contacts()
            logger.info(f"Custom name removed for {phone_number}")
    
    def get_all_contacts(self) -> Dict[str, str]:
        """Get all contacts mapping phone_number -> name"""
        return self.contacts.copy()
    
    def search_contact_by_name(self, name: str) -> Optional[str]:
        """Find phone number by name (case insensitive)"""
        name_lower = name.lower().strip()
        for phone, contact_name in self.contacts.items():
            if contact_name.lower() == name_lower:
                return phone
        return None
    
    def update_contact_from_webhook(self, phone_number: str, webhook_name: str = None) -> str:
        """Update contact from webhook data, preserve custom names"""
        # If we already have a custom name, use it
        if phone_number in self.contacts:
            return self.contacts[phone_number]
        
        # If webhook provided a name and we don't have a custom one, use webhook name
        if webhook_name and webhook_name.strip():
            self.set_contact_name(phone_number, webhook_name.strip())
            return webhook_name.strip()
        
        # Otherwise return phone number
        return phone_number

# Global instance
contact_service = ContactService()