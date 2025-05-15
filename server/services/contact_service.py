import json
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class ContactService:
    def __init__(self, contacts_file: str = None):
        """Initialize contact service with persistent storage"""
        if contacts_file is None:
            # Use absolute path relative to this file's location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            contacts_file = os.path.join(base_dir, "contacts.json")
        self.contacts_file = contacts_file
        logger.info(f"ContactService initialized with file: {self.contacts_file}")
        self.contacts = self._load_contacts()
        logger.info(f"Loaded {len(self.contacts)} contacts from file")

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone numbers for consistent storage and lookup.

        This strips non-digit characters and preserves the full digit string.
        For matching it is helpful to also compare suffixes (last 10 digits).
        """
        if not phone:
            return ""
        # Keep only digits
        digits = ''.join(ch for ch in str(phone) if ch.isdigit())
        return digits
    
    def _load_contacts(self) -> Dict[str, str]:
        """Load contacts from JSON file"""
        try:
            if os.path.exists(self.contacts_file):
                with open(self.contacts_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    # Normalize keys on load so stored keys are consistent
                    normalized = {}
                    for k, v in (raw or {}).items():
                        nk = self._normalize_phone(k)
                        if not nk:
                            continue
                        # Support old format where value was a string name
                        # ALL existing contacts are treated as user_defined=True (manually set)
                        if isinstance(v, str):
                            normalized[nk] = {"name": v, "user_defined": True}
                        elif isinstance(v, dict):
                            # If dict present, ensure keys exist
                            # Force user_defined to True for all existing contacts to protect them
                            name = v.get("name") or ""
                            normalized[nk] = {"name": name, "user_defined": True}
                        else:
                            # Fallback: stringify
                            normalized[nk] = {"name": str(v), "user_defined": True}
                    return normalized
            return {}
        except Exception as e:
            logger.error(f"Error loading contacts: {e}")
            return {}
    
    def _save_contacts(self) -> None:
        """Save contacts to JSON file"""
        try:
            with open(self.contacts_file, 'w', encoding='utf-8') as f:
                # Ensure keys are normalized when saving. Store as dicts with name and user_defined flag.
                json.dump(self.contacts, f, indent=2, ensure_ascii=False)
            logger.info(f"Contacts saved to {self.contacts_file}")
        except Exception as e:
            logger.error(f"Error saving contacts: {e}")
    
    def get_contact_name(self, phone_number: str) -> str:
        """Get contact name, return phone number if no custom name is set"""
        nk = self._normalize_phone(phone_number)
        if not nk:
            return phone_number
        # Direct match
        if nk in self.contacts:
            entry = self.contacts[nk]
            return entry.get("name") or phone_number
        # Try suffix match (last 10 digits)
        suffix = nk[-10:]
        for phone, name in self.contacts.items():
            if phone.endswith(suffix):
                # name may be dict
                if isinstance(name, dict):
                    return name.get("name") or phone_number
                return name
        # Fallback to provided number
        return phone_number
    
    def set_contact_name(self, phone_number: str, name: str) -> None:
        """Set contact name and save to file"""
        if name and name.strip():
            nk = self._normalize_phone(phone_number)
            if not nk:
                logger.warning(f"Attempted to set name for invalid phone: {phone_number}")
                return
            # Store as dict with user_defined flag so webhooks don't overwrite
            self.contacts[nk] = {"name": name.strip(), "user_defined": True}
            self._save_contacts()
            logger.info(f"Contact {phone_number} renamed to '{name}'")
        else:
            logger.warning(f"Attempted to set empty name for {phone_number}")
    
    def remove_contact_name(self, phone_number: str) -> None:
        """Remove custom name for contact (will revert to phone number)"""
        nk = self._normalize_phone(phone_number)
        if nk and nk in self.contacts:
            del self.contacts[nk]
            self._save_contacts()
            logger.info(f"Custom name removed for {phone_number}")
    
    def get_all_contacts(self) -> Dict[str, str]:
        """Get all contacts mapping phone_number -> name"""
        # Return a copy mapping in normalized digits -> name (string)
        out = {}
        for k, v in self.contacts.items():
            if isinstance(v, dict):
                out[k] = v.get("name") or ""
            else:
                out[k] = v
        return out
    
    def search_contact_by_name(self, name: str) -> Optional[str]:
        """Find phone number by name (case insensitive)"""
        name_lower = name.lower().strip()
        for phone, contact_entry in self.contacts.items():
            contact_name = contact_entry.get("name") if isinstance(contact_entry, dict) else contact_entry
            if (contact_name or "").lower() == name_lower:
                return phone
        return None
    
    def update_contact_from_webhook(self, phone_number: str, webhook_name: str = None) -> str:
        """Get contact name from webhook - NEVER modifies existing contacts, only adds new ones"""
        nk = self._normalize_phone(phone_number)
        
        logger.info(f"[WEBHOOK] Processing: phone={phone_number}, normalized={nk}, webhook_name={webhook_name}")
        logger.info(f"[WEBHOOK] Current contacts: {list(self.contacts.keys())}")
        
        # RULE 1: If we already have an exact match, return it and DO NOT update
        if nk in self.contacts:
            entry = self.contacts[nk]
            existing_name = entry.get("name") if isinstance(entry, dict) else entry
            logger.info(f"[WEBHOOK] EXACT MATCH FOUND - Returning existing name: {existing_name}")
            logger.info(f"[WEBHOOK] NO CHANGES MADE TO CONTACTS")
            return existing_name

        # RULE 2: Try suffix match (last 10 digits) to find an existing contact
        # If found, map the new key to the existing name (links different phone formats)
        # but DO NOT modify the existing entry
        suffix = nk[-10:]
        logger.info(f"[WEBHOOK] No exact match, trying suffix match with: {suffix}")
        for phone, entry in self.contacts.items():
            if phone.endswith(suffix):
                existing_name = entry.get("name") if isinstance(entry, dict) else entry
                user_def = entry.get("user_defined") if isinstance(entry, dict) else True
                logger.info(f"[WEBHOOK] SUFFIX MATCH FOUND - phone={phone}, name={existing_name}")
                # Map the new normalized key to the existing name for future lookups
                try:
                    self.contacts[nk] = {"name": existing_name, "user_defined": user_def}
                    self._save_contacts()
                    logger.info(f"[WEBHOOK] Created alias {nk} -> {existing_name}")
                except Exception as e:
                    logger.error(f"[WEBHOOK] Failed to save alias: {e}")
                return existing_name

        # RULE 3: Only if no existing contact is found (exact or suffix), then and ONLY then
        # add a new contact using the webhook-provided name
        logger.info(f"[WEBHOOK] NO MATCH FOUND - This is a new contact")
        if webhook_name and webhook_name.strip():
            try:
                self.contacts[nk] = {"name": webhook_name.strip(), "user_defined": False}
                self._save_contacts()
                logger.info(f"[WEBHOOK] New contact added: {nk} -> {webhook_name.strip()}")
            except Exception as e:
                logger.error(f"[WEBHOOK] Failed to add new contact: {e}")
            return webhook_name.strip()

        # Otherwise return the phone number
        logger.info(f"[WEBHOOK] No webhook name provided, returning phone: {phone_number}")
        return phone_number

# Global instance
contact_service = ContactService()