# ⚙️ FairShift — Decent Work for Every Worker

> **UN SDG 8: Decent Work and Economic Growth**
>
> A lightweight workforce-management platform for **College Campus Support Staff** and **Construction Workers** designed for serverless cloud deployment.

---

## 🎯 Problem
Informal-sector workers (campus support staff, site labourers) face manual paper attendance tracking, zero anonymous channels to report hazards, and no digital auditable records.

## 🛠️ FairShift Solution
- **Shift Tracking:** Real-time clock-in/out timestamps.
- **Safety Reporting:** Anonymous hazard reports with Web Speech API voice dictation.
- **Admin Dashboard:** Live attendance tracking and hazard escalation workflows.
- **Accessibility:** Dual-language labels (English + Tamil), high-contrast touch targets, screen-reader compliance.

---

## 🏗️ Architecture (Vercel Serverless + Cloud PostgreSQL)
- **Runtime:** Vercel Python Serverless Functions (`@vercel/python`)
- **Database:** Cloud PostgreSQL (Neon, Supabase, AWS RDS, etc.)
- **Configuration:** `vercel.json` routing all routes to `app.py`
- **Security:** Zero hard-coded credentials; uses `DATABASE_URL` and `FLASK_SECRET_KEY` from environment variables.

---

## 🚀 Quick Setup & Deployment

### 1. Configure Cloud Database
Obtain a cloud PostgreSQL connection string and initialize schema:
```bash
$env:DATABASE_URL="postgres://user:password@ep-host.region.aws.neon.tech/fairshift?sslmode=require"
python init_db.py
```

### 2. Run Tests
```bash
python test_app.py
```

### 3. Deploy to Vercel
1. Set `DATABASE_URL` in your Vercel Project Environment Variables.
2. Deploy:
```bash
vercel --prod
```
