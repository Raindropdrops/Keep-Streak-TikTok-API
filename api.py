from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import os
from utils import load_contacts, save_contacts

app = FastAPI(title="TikTok Streak Auto API", version="2.0.0")

class ContactUpdateSchema(BaseModel):
    aliases: Optional[List[str]] = None
    enabled: Optional[bool] = None
    user_id: Optional[str] = None
    sec_uid: Optional[str] = None
    conversation_id: Optional[str] = None
    profile_url: Optional[str] = None
    display_name: Optional[str] = None

def bg_resolve_contacts():
    from utils import init_browser, login_tiktok, resolve_contacts_flow
    browser = None
    try:
        print("[API Background Task] Starting contact resolution...")
        browser, wait = init_browser()
        login_tiktok(browser, wait, os.getenv("TIKTOK_USERNAME"), os.getenv("TIKTOK_PASSWORD"))
        resolve_contacts_flow(browser, wait)
        print("[API Background Task] Contact resolution completed successfully.")
    except Exception as e:
        print(f"[API Background Task] Error during contact resolution: {e}")
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass

@app.get("/v1/contacts")
def get_contacts():
    contacts = load_contacts()
    enhanced_contacts = []
    for c in contacts:
        resolved = bool(c.get("last_resolved_at"))
        enhanced = {
            **c,
            "resolved": resolved,
            "resolve_status": "resolved" if resolved else "unresolved"
        }
        enhanced_contacts.append(enhanced)
    return enhanced_contacts

@app.post("/v1/contacts/resolve", status_code=status.HTTP_202_ACCEPTED)
def trigger_resolve(background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_resolve_contacts)
    return {"message": "Contact resolution started in the background"}

@app.patch("/v1/contacts/{identifier}")
def update_contact(identifier: str, payload: ContactUpdateSchema):
    contacts = load_contacts()
    matched_contact = None
    
    # Search by username, user_id, or conversation_id
    for c in contacts:
        if c.get("username") == identifier or \
           c.get("user_id") == identifier or \
           c.get("conversation_id") == identifier:
            matched_contact = c
            break
            
    if not matched_contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Contact with identifier '{identifier}' not found"
        )
        
    # Apply updates
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        matched_contact[key] = value
        
    save_contacts(contacts)
    return matched_contact
