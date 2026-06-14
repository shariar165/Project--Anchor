"""
Built-in sample legal corpus for Anchor AI demo / development.

Contains key Bangladesh statutes, procedural workflows, and DIU campus policies.
Load with: python -m app.ai.sample_corpus
Or via API: POST /ai/ingest (dev only)
"""

CORPUS: list[dict] = [

    # ── Penal Code 1860 ──────────────────────────────────────────────────────

    {
        "chunk_id": "pc1860-354",
        "document_title": "Penal Code 1860",
        "hierarchy": "Penal Code 1860 › Chapter XVI › Section 354",
        "effective_date": "1860-10-06",
        "amendment_status": "current",
        "text": (
            "Section 354 — Assault or criminal force to woman with intent to outrage her modesty.\n"
            "Whoever assaults or uses criminal force to any woman, intending to outrage or knowing "
            "it to be likely that he will thereby outrage her modesty, shall be punished with "
            "imprisonment of either description for a term which may extend to two years, or with "
            "fine, or with both. This section applies to physical contact, grabbing, and forceful "
            "touching against a woman's will in public or private spaces."
        ),
        "metadata": {
            "chunk_id": "pc1860-354",
            "document_id": "pc1860",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Penal Code 1860",
            "chapter": "XVI",
            "section": "354",
            "effective_date": "1860-10-06",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "pc1860-509",
        "document_title": "Penal Code 1860",
        "hierarchy": "Penal Code 1860 › Chapter XXII › Section 509",
        "effective_date": "1860-10-06",
        "amendment_status": "current",
        "text": (
            "Section 509 — Word, gesture or act intended to insult the modesty of a woman.\n"
            "Whoever, intending to insult the modesty of any woman, utters any word, makes any "
            "sound or gesture, or exhibits any object intending that such word or sound shall be "
            "heard, or that such gesture or object shall be seen, by such woman, or intrudes upon "
            "the privacy of such woman, shall be punished with simple imprisonment for a term "
            "which may extend to one year, or with fine, or with both.\n"
            "This section covers eve-teasing, street harassment, whistling, making remarks, and "
            "any gesture that a reasonable woman would find insulting. It applies in public spaces, "
            "workplaces, and educational institutions."
        ),
        "metadata": {
            "chunk_id": "pc1860-509",
            "document_id": "pc1860",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Penal Code 1860",
            "chapter": "XXII",
            "section": "509",
            "effective_date": "1860-10-06",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "pc1860-390-392",
        "document_title": "Penal Code 1860",
        "hierarchy": "Penal Code 1860 › Chapter XVII › Sections 390–392",
        "effective_date": "1860-10-06",
        "amendment_status": "current",
        "text": (
            "Section 390 — Robbery definition.\n"
            "In all robbery there is either theft or extortion. Theft is robbery if in order "
            "to commit theft, or in committing theft, or in carrying away property obtained by "
            "theft, the offender voluntarily causes or attempts to cause to any person death, "
            "hurt, or wrongful restraint, or fear of instant death, hurt, or wrongful restraint.\n\n"
            "Section 392 — Punishment for robbery.\n"
            "Whoever commits robbery shall be punished with rigorous imprisonment for a term "
            "which may extend to ten years. Mobile phone snatching by force or threat qualifies "
            "as robbery (not mere theft) under Section 390 when the accused uses force while "
            "taking the property, even momentarily.\n\n"
            "Section 379 — Theft (simpler case without force).\n"
            "Punishment: imprisonment up to three years, or fine, or both. Applies when property "
            "is taken without the owner's knowledge and without force."
        ),
        "metadata": {
            "chunk_id": "pc1860-390-392",
            "document_id": "pc1860",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Penal Code 1860",
            "chapter": "XVII",
            "section": "390",
            "effective_date": "1860-10-06",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "pc1860-326",
        "document_title": "Penal Code 1860",
        "hierarchy": "Penal Code 1860 › Chapter XVI › Section 326",
        "effective_date": "1860-10-06",
        "amendment_status": "current",
        "text": (
            "Section 326 — Voluntarily causing grievous hurt by dangerous weapons or means.\n"
            "Whoever, except in the case provided for by Section 335, voluntarily causes grievous "
            "hurt by means of any instrument for shooting, stabbing or cutting, or any instrument "
            "which, used as a weapon of offence, is likely to cause death, or by means of fire or "
            "any heated substance, or by means of any poison or any corrosive substance, or by "
            "means of any explosive substance or by means of any substance which it is deleterious "
            "to the human body to inhale, to swallow, or to receive into the blood, shall be "
            "punished with imprisonment for life, or with imprisonment of either description for "
            "a term which may extend to ten years, and shall also be liable to fine."
        ),
        "metadata": {
            "chunk_id": "pc1860-326",
            "document_id": "pc1860",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Penal Code 1860",
            "chapter": "XVI",
            "section": "326",
            "effective_date": "1860-10-06",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },

    # ── Code of Criminal Procedure 1898 ─────────────────────────────────────

    {
        "chunk_id": "crpc-154-155",
        "document_title": "Code of Criminal Procedure 1898",
        "hierarchy": "CrPC 1898 › Chapter XII › Sections 154–155",
        "effective_date": "1898-01-01",
        "amendment_status": "current",
        "text": (
            "Section 154 — Information in cognizable cases (FIR).\n"
            "(1) Every information relating to the commission of a cognizable offence, if given "
            "orally to an officer in charge of a police station, shall be reduced to writing by "
            "him and be read over to the informant. Every such information shall be signed by the "
            "person giving it.\n"
            "(2) A copy of the information as recorded shall be given forthwith, free of cost, "
            "to the informant.\n\n"
            "Section 155 — Information as to non-cognizable cases (General Diary).\n"
            "When information is given to an officer in charge of a police station of the "
            "commission within the local limits of his station of a non-cognizable offence, he "
            "shall enter or cause to be entered the substance of such information in a book to "
            "be kept in such manner as the Government may prescribe. A General Diary (GD) is "
            "the entry under this section — it is free, must be accepted, and forms the "
            "official first record of non-cognizable offences like phone theft, minor disputes."
        ),
        "metadata": {
            "chunk_id": "crpc-154-155",
            "document_id": "crpc1898",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Code of Criminal Procedure 1898",
            "chapter": "XII",
            "section": "154",
            "effective_date": "1898-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "crpc-60a-constitution-33",
        "document_title": "Code of Criminal Procedure 1898 & Constitution of Bangladesh",
        "hierarchy": "CrPC § 60A · Constitution Art. 33",
        "effective_date": "1972-12-16",
        "amendment_status": "current",
        "text": (
            "Rights on arrest — CrPC Section 60A & Constitution Article 33.\n"
            "On arrest, a person has the following rights:\n"
            "1. To be informed of the grounds of arrest immediately.\n"
            "2. To consult a lawyer of their own choice (constitutional guarantee).\n"
            "3. To have a relative or friend informed of the arrest.\n"
            "4. To be produced before a magistrate within 24 hours of arrest (excluding travel).\n"
            "5. Not to be subjected to torture, cruel, inhuman or degrading treatment.\n"
            "6. To remain silent — no confession extracted by force is admissible.\n"
            "Violation of these rights can be challenged via High Court writ petition "
            "under Constitution Article 44."
        ),
        "metadata": {
            "chunk_id": "crpc-60a-constitution-33",
            "document_id": "crpc1898",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 1,
            "act_name": "CrPC / Constitution of Bangladesh",
            "chapter": "",
            "section": "60A / Art.33",
            "effective_date": "1972-12-16",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },

    # ── Domestic Violence (Prevention and Protection) Act 2010 ───────────────

    {
        "chunk_id": "dva2010-full",
        "document_title": "Domestic Violence (Prevention and Protection) Act 2010",
        "hierarchy": "DV Act 2010 › Sections 2–10",
        "effective_date": "2010-10-05",
        "amendment_status": "current",
        "text": (
            "Domestic Violence (Prevention and Protection) Act 2010.\n\n"
            "Section 2 — Definitions.\n"
            "'Domestic violence' means physical abuse, psychological abuse, sexual abuse, "
            "economic abuse, or stalking committed by a family member against another family "
            "member. Family members include spouses, parents, children, siblings, and any "
            "person living in the same household.\n\n"
            "Section 5 — Right to apply for orders.\n"
            "Any victim of domestic violence, or any person acting on their behalf, may apply "
            "to a Magistrate for relief. No court fee is required.\n\n"
            "Section 8 — Types of orders available.\n"
            "(a) Protection order — prevents the respondent from committing further violence.\n"
            "(b) Residence order — allows the victim to remain in the shared residence.\n"
            "(c) Monetary relief — for medical expenses, loss of earnings, and mental anguish.\n"
            "(d) Custody order — for minor children.\n\n"
            "Section 9 — Emergency protection order.\n"
            "A Magistrate may pass an interim protection order on the same day of application "
            "if the victim's life or safety is in immediate danger."
        ),
        "metadata": {
            "chunk_id": "dva2010-full",
            "document_id": "dva2010",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Domestic Violence (Prevention and Protection) Act 2010",
            "chapter": "",
            "section": "2-10",
            "effective_date": "2010-10-05",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },

    # ── Cyber Security Act 2023 ──────────────────────────────────────────────

    {
        "chunk_id": "csa2023-25-29",
        "document_title": "Cyber Security Act 2023",
        "hierarchy": "Cyber Security Act 2023 › Sections 25–29",
        "effective_date": "2023-09-18",
        "amendment_status": "current",
        "text": (
            "Cyber Security Act 2023 — Harassment and defamation offences.\n\n"
            "Section 25 — Publishing defamatory information.\n"
            "Whoever, using digital devices, intentionally publishes false information about "
            "any person, or makes defamatory statements, or causes mental suffering, commits "
            "an offence punishable with imprisonment up to 3 years and/or fine up to Tk 3 lakh.\n\n"
            "Section 26 — Identity theft.\n"
            "Unlawful collection, publication, or supply of identifying information is punishable "
            "with imprisonment up to 5 years and/or fine up to Tk 5 lakh.\n\n"
            "Section 29 — Online sexual harassment.\n"
            "Targeted sexual harassment of women using digital means is a cognizable, "
            "non-bailable offence. Punishment: imprisonment up to 7 years and/or fine up to "
            "Tk 5 lakh. Repeat offence: up to 10 years.\n\n"
            "Filing procedure: Complainants may file at the Cyber Crime Unit (CID Bangladesh "
            "Police), Cyber Police Centre (Dhaka), or any police station — which will forward "
            "the complaint to the Cyber Tribunal, Dhaka."
        ),
        "metadata": {
            "chunk_id": "csa2023-25-29",
            "document_id": "csa2023",
            "document_type": "statute",
            "jurisdiction": "bangladesh",
            "authority_rank": 2,
            "act_name": "Cyber Security Act 2023",
            "chapter": "",
            "section": "25",
            "effective_date": "2023-09-18",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },

    # ── Workflow Documents ────────────────────────────────────────────────────

    {
        "chunk_id": "wf-gd-filing",
        "document_title": "Workflow: How to File a General Diary (GD)",
        "hierarchy": "Workflow › Police › GD Filing",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "WORKFLOW — How to file a General Diary (GD) at a police station.\n\n"
            "When to use a GD (not FIR):\n"
            "- Phone snatching, minor theft, property dispute as first record\n"
            "- Harassment not yet escalated to FIR\n"
            "- Any incident you want officially on record\n\n"
            "Step 1: Go to the police station (thana) nearest to where the incident occurred. "
            "You do not need a lawyer for a GD.\n"
            "Step 2: Ask to file a General Diary. The Duty Officer MUST accept it (Section 155 CrPC). "
            "It is free — pay nothing.\n"
            "Step 3: Bring with you:\n"
            "  • Your National ID Card (NID) or Passport\n"
            "  • Written description of incident: date, time, location, description of suspects\n"
            "  • For phone theft: IMEI number (*#06# on any phone, or printed on box), "
            "SIM number, purchase invoice if available\n"
            "  • For harassment: screenshots, chat logs, or names of witnesses\n"
            "Step 4: The officer enters the details in the GD Register and gives you a GD number.\n"
            "Step 5: Ask for a certified copy of the GD — free of cost under CrPC.\n"
            "Step 6: If police refuse to accept the GD: Contact the Officer-in-Charge (OC) or "
            "the Superintendent of Police (SP). You may also apply directly to the Magistrate.\n\n"
            "Timeline: Accepted same day. For urgent matters (robbery, assault) investigation "
            "begins within 24–72 hours.\n"
            "Cost: Always free."
        ),
        "metadata": {
            "chunk_id": "wf-gd-filing",
            "document_id": "wf-gd",
            "document_type": "workflow",
            "jurisdiction": "bangladesh",
            "authority_rank": 5,
            "act_name": "Workflow: GD Filing",
            "chapter": "",
            "section": "",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "wf-fir-filing",
        "document_title": "Workflow: How to File an FIR",
        "hierarchy": "Workflow › Police › FIR",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "WORKFLOW — How to file a First Information Report (FIR).\n\n"
            "FIR vs GD:\n"
            "- FIR: For cognizable offences (robbery, rape, murder, kidnapping, grievous hurt). "
            "Police MUST investigate.\n"
            "- GD: For non-cognizable offences or as initial record.\n\n"
            "Step 1: Go to the thana covering the area where the offence occurred.\n"
            "Step 2: Give a written or oral complaint of the cognizable offence.\n"
            "Step 3: The officer MUST register the FIR immediately (Section 154 CrPC). "
            "Police cannot refuse to register an FIR for a cognizable offence.\n"
            "Step 4: You receive a signed copy of the FIR — free of cost.\n"
            "Step 5: If police refuse to register FIR: Apply directly to the Magistrate "
            "(Section 156(3) CrPC). The Magistrate can order police to investigate.\n\n"
            "After FIR:\n"
            "- Police must file charge-sheet within 60 days (120 for complex cases)\n"
            "- If charge-sheet filed → case goes to court\n"
            "- If police close case → you can contest the Final Report in court\n\n"
            "Important: An FIR is the start of investigation, not a conviction."
        ),
        "metadata": {
            "chunk_id": "wf-fir-filing",
            "document_id": "wf-fir",
            "document_type": "workflow",
            "jurisdiction": "bangladesh",
            "authority_rank": 5,
            "act_name": "Workflow: FIR Filing",
            "chapter": "",
            "section": "",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "wf-dv-protection",
        "document_title": "Workflow: Domestic Violence Protection Order",
        "hierarchy": "Workflow › Court › DV Protection Order",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "WORKFLOW — How to get a Domestic Violence Protection Order.\n\n"
            "Step 1: Go to the nearest Magistrate Court, OR file through a legal aid "
            "organisation (free, see below).\n"
            "Step 2: Bring: NID, medical reports of injuries, photos, witness statements, "
            "any threatening messages or documents.\n"
            "Step 3: File Form A (Protection Order Application). No court fee.\n"
            "Step 4: The Magistrate holds an emergency hearing — can be same day in urgent cases.\n"
            "Step 5: Interim protection order can be granted within hours.\n"
            "Step 6: Full hearing within 90 days where both sides present their case.\n\n"
            "Free legal aid organisations:\n"
            "- Bangladesh Legal Aid Services Trust (BLAST): 02-9880064\n"
            "- National Legal Aid Services Organisation (NLASO): 16430\n"
            "- Ain o Salish Kendra (ASK): 02-9511679\n\n"
            "If in immediate danger: Go to police station first (GD or FIR), then apply for "
            "DV protection order. Police can also refer you to a shelter home."
        ),
        "metadata": {
            "chunk_id": "wf-dv-protection",
            "document_id": "wf-dv",
            "document_type": "workflow",
            "jurisdiction": "bangladesh",
            "authority_rank": 5,
            "act_name": "Workflow: DV Protection Order",
            "chapter": "",
            "section": "",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },
    {
        "chunk_id": "wf-cyber-complaint",
        "document_title": "Workflow: Filing a Cyber Harassment Complaint",
        "hierarchy": "Workflow › Police › Cyber Complaint",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "WORKFLOW — How to file a cyber harassment complaint.\n\n"
            "Step 1: Preserve all evidence FIRST:\n"
            "  • Screenshots of all harassing content (with timestamps visible)\n"
            "  • URLs, usernames, account links\n"
            "  • Any identifying information of the harasser\n"
            "  • Export chat logs if possible\n\n"
            "Step 2: Report the accounts to the platform (Facebook, Instagram, etc.) and "
            "request account suspension. Keep the reference number.\n\n"
            "Step 3: File a complaint at ONE of:\n"
            "  (a) Cyber Crime Unit, CID Bangladesh Police, Dhaka (03-9330083)\n"
            "  (b) Cyber Police Centre, Dhaka Metropolitan Police (DMP)\n"
            "  (c) Any police station (they forward to cyber unit)\n\n"
            "Step 4: Bring all evidence (screenshots printout + digital copy on USB), your "
            "NID, and a written description of the harassment.\n"
            "Step 5: Get GD/FIR number and case reference.\n\n"
            "Applicable law: Cyber Security Act 2023, Sections 25–29.\n"
            "Timeline: Initial response within 24–48 hours for urgent cases.\n"
            "Free legal support: Cyber Help Desk, Police Headquarters."
        ),
        "metadata": {
            "chunk_id": "wf-cyber-complaint",
            "document_id": "wf-cyber",
            "document_type": "workflow",
            "jurisdiction": "bangladesh",
            "authority_rank": 5,
            "act_name": "Workflow: Cyber Harassment Complaint",
            "chapter": "",
            "section": "",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "national",
        },
    },

    # ── DIU Campus Policies ──────────────────────────────────────────────────

    {
        "chunk_id": "diu-complaint-procedure",
        "document_title": "DIU Student Complaint Procedure",
        "hierarchy": "DIU Student Code 2024 › Section 3.4",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "DIU Student Complaint Procedure — Student Code 2024, Section 3.4.\n\n"
            "Who to contact:\n"
            "  • Hostel issues (AC, plumbing, mess): Floor Warden → Hostel Provost → DSA\n"
            "  • Classroom issues (projector, AC, internet): Dept. Head → Dean\n"
            "  • Academic issues (grades, leave): Dept. Head → Controller of Exams\n"
            "  • Harassment or misconduct: Proctor's Office (first point of contact)\n"
            "  • Any issue: Anchor platform (anonymous filing available)\n\n"
            "How to file:\n"
            "  1. Write complaint addressed to the relevant office\n"
            "  2. Submit via Anchor platform OR physically to the office\n"
            "  3. Anonymous complaints are accepted — identity kept confidential\n\n"
            "Timelines:\n"
            "  • Acknowledgement: within 3 working days\n"
            "  • Resolution (standard): within 21 working days\n"
            "  • Resolution (urgent/safety): within 7 working days\n\n"
            "Escalation path: Warden → DSA → Proctor → VC Office → University Grievance Committee\n\n"
            "Note: Anonymous complaints are accepted but may limit the scope of investigation."
        ),
        "metadata": {
            "chunk_id": "diu-complaint-procedure",
            "document_id": "diu-code-2024",
            "document_type": "university_policy",
            "jurisdiction": "bangladesh",
            "authority_rank": 4,
            "act_name": "DIU Student Code 2024",
            "chapter": "3",
            "section": "3.4",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "diu",
        },
    },
    {
        "chunk_id": "diu-hostel-service-standards",
        "document_title": "DIU Hostel Service Standards",
        "hierarchy": "DIU Hostel Regulations 2024 › Clause 12",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "DIU Hostel Service Standards — Clause 12.\n\n"
            "Maintenance response time commitments:\n"
            "  • AC / essential utilities: 3 working days\n"
            "  • General maintenance (plumbing, electrical): 7 working days\n"
            "  • Structural or safety issues: escalated to administration within 24 hours\n\n"
            "Escalation procedure for unresolved hostel issues:\n"
            "  1. Report verbally or in writing to Floor Warden\n"
            "  2. If no response within 3 working days → Written complaint to Hostel Provost\n"
            "  3. If still unresolved → Escalate to DSA (Dean of Student Affairs)\n"
            "  4. Final escalation: VC Office → University Grievance Committee\n\n"
            "Student rights:\n"
            "  • Right to request written confirmation of complaint receipt\n"
            "  • Right to know the expected resolution date\n"
            "  • Repeated unresolved complaints may be raised with the Grievance Committee\n\n"
            "If an AC has been broken for more than 3 working days without repair, the student "
            "has grounds to file a formal complaint with the Hostel Provost and, if needed, escalate to DSA."
        ),
        "metadata": {
            "chunk_id": "diu-hostel-service-standards",
            "document_id": "diu-hostel-regs-2024",
            "document_type": "university_policy",
            "jurisdiction": "bangladesh",
            "authority_rank": 4,
            "act_name": "DIU Hostel Service Standards",
            "chapter": "",
            "section": "12",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "diu",
        },
    },
    {
        "chunk_id": "diu-academic-leave",
        "document_title": "DIU Academic Leave Policy",
        "hierarchy": "DIU Academic Regulations 2024 › Section 7",
        "effective_date": "2024-01-01",
        "amendment_status": "current",
        "text": (
            "DIU Academic Leave Policy — Section 7.\n\n"
            "Types of academic leave:\n"
            "  • Medical leave: Up to 14 days (attach doctor's certificate or hospital admission slip)\n"
            "  • Family emergency: Up to 7 days (at Department Head's discretion)\n"
            "  • Exam/competition leave: Up to 5 days (attach invitation letter)\n"
            "  • Semester leave: Applied to Registrar's office minimum 30 days in advance\n\n"
            "How to apply:\n"
            "  1. Write application to Head of Department\n"
            "  2. Attach supporting documents (medical certificate, event invitation, etc.)\n"
            "  3. Submit via Anchor platform or physically to department office\n"
            "  4. Expected response: 2–3 working days\n\n"
            "Approved leave: Student must inform course instructors via email and arrange "
            "to make up missed work.\n"
            "Leave without approval: Attendance shortage affects examination eligibility "
            "(minimum 75% attendance required per semester)."
        ),
        "metadata": {
            "chunk_id": "diu-academic-leave",
            "document_id": "diu-academic-regs-2024",
            "document_type": "university_policy",
            "jurisdiction": "bangladesh",
            "authority_rank": 4,
            "act_name": "DIU Academic Regulations 2024",
            "chapter": "",
            "section": "7",
            "effective_date": "2024-01-01",
            "amendment_status": "current",
            "language": "en",
            "tenant_scope": "diu",
        },
    },
]


async def load_sample_corpus(generate_prefixes: bool = False) -> int:
    """
    Load the built-in sample corpus into ChromaDB and BM25 indices.
    generate_prefixes=False for fast load (skips LLM prefix generation).
    """
    from app.pipeline.ingestion import ingest_document
    import logging
    logger = logging.getLogger(__name__)

    national = [c for c in CORPUS if c["metadata"].get("tenant_scope") == "national"]
    campus = [c for c in CORPUS if c["metadata"].get("tenant_scope") == "diu"]

    total = 0
    if national:
        logger.info("Ingesting %d national corpus chunks…", len(national))
        total += await ingest_document(national, namespace="national", generate_prefixes=generate_prefixes)

    if campus:
        logger.info("Ingesting %d campus corpus chunks (DIU)…", len(campus))
        total += await ingest_document(campus, namespace="diu", generate_prefixes=generate_prefixes)

    logger.info("Sample corpus fully loaded: %d chunks.", total)
    return total


if __name__ == "__main__":
    import asyncio
    asyncio.run(load_sample_corpus())
