# NexPal – AI-Powered Facilities Workflow & SLA Management System

## Overview
NexPal is an AI-powered facilities operations platform that automates complaint management, SLA tracking, WhatsApp notifications, escalation workflows, and operational analytics.

The system uses OpenAI GPT models to classify employee complaints & queries related to facilities management, assign priorities, detect locations, and automatically route tickets to the appropriate service departments.

---

## Features

- AI-powered complaint classification
- Automated department routing
- SLA countdown tracking
- SLA breach escalation
- WhatsApp service notifications
- Ticket lifecycle management
- Real-time admin dashboard
- Inventory tracking system
- Vendor AMC lifecycle monitoring
- Operational insights & analytics

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | Python |
| Database | SQLite |
| AI Engine | OpenAI GPT-4o |
| Messaging | Twilio WhatsApp API |
| Visualization | Plotly |
| Data Processing | Pandas |

---

## Workflow

Employee Complaint → AI Classification → Department Routing → WhatsApp Notification → SLA Tracking → Escalation → Dashboard Monitoring → Ticket Closure

---

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Future Enhancements

- Service Team acknowledgment system
- Employee closure confirmation
- RAG-based SOP assistant
- Predictive maintenance analytics
- Mobile application support
- Production WhatsApp Business API integration