---
name: uni-admin-application
description: >
  Use this skill whenever a student needs to write a formal application letter to university
  administration. Triggers: "write an application", "application for late fee", "overlap exam",
  "registration permission", "exam permission", "mid/final exam permission", "ID card extension",
  "late degree approval", "application to registrar/HOD/dean", "attendance shortage", "semester
  freeze", "fee waiver", "re-admission", "leave application", "result correction", "bonafide
  certificate", "application for hostel/transcript", or ANY student writing a formal request to
  a university authority. Always trigger even for casual phrasings like "help me write something
  for my uni" or "I need to ask my college for permission". Supports custom formats — when the
  user uploads a university form or template, use it to structure the output.
---

# University Formal Application Writer

A skill for writing professional, respectful formal application letters that students submit
to university administration, registrars, department heads, deans, or examination committees.

---

## Step 1 — Identify the Application Type

Check the user's message and map it to a type. If unclear, ask ONE question:

> "What is your application for? (e.g. late fee payment, exam permission, registration, overlap exam, ID card, degree approval, etc.)"

### Supported Application Types

| Type | Reference File |
|---|---|
| Late Fee Payment | `references/late-fee-payment.md` |
| Overlap / Clash Exam | `references/overlap-exam.md` |
| Registration Permission | `references/registration-permission.md` |
| Mid / Final Exam Permission | `references/exam-permission.md` |
| Late Degree Approval | `references/late-degree-approval.md` |
| ID Card Extension / Renewal | `references/id-card-extension.md` |
| Attendance Shortage / Leave | `references/attendance-leave.md` |
| Semester Freeze / Drop | `references/semester-freeze.md` |
| Fee Waiver / Concession | `references/fee-waiver.md` |
| Re-admission | `references/readmission.md` |
| General / Custom Application | `references/general-application.md` |

Read the relevant reference file before writing.

> **If the user uploads a university form or format file**: Read it carefully and use
> its structure, headings, and required fields to shape the output. Their format takes
> priority over the default structure.

---

## Step 2 — Gather Student Information

Ask only what's missing. Extract anything already provided.

### Always Required
- **Full name** of the student
- **Student ID / Roll number**
- **Department / Program / Session**
- **Recipient** (The Registrar / Head of Department / Controller of Examinations / Dean)
- **Reason / justification** for the request (the core story)
- **Specific request** (what action they want taken)

### Situational
- **Course name / code** (for exam or registration applications)
- **Exam date / semester** (for exam-related applications)
- **Fee amount / challan details** (for fee applications)
- **Supporting documents available** (medical certificate, bank statement, etc.)
- **Previous attempts** (has the student applied before?)

If the student gives a brief reason like "I was sick" or "financial problem" — build the
narrative professionally without asking them to elaborate unless absolutely needed.

---

## Step 3 — Write the Application

### Standard Pakistani/South Asian University Format

```
Date: [DD Month YYYY]

To,
The [Recipient Title],
[Department/Office Name],
[University Name].

Subject: Application for [Purpose] — [Student Name] | [ID/Roll No.]

Respected Sir/Madam,

[Body paragraphs]

I, therefore, humbly request you to kindly [specific action requested].

I shall be highly obliged for your kind consideration.

Yours obediently,
[Student Full Name]
[Student ID / Roll No.]
[Program / Department]
[Contact Number / Email]
[Date]
```

### Body Structure (3–4 paragraphs)

**Paragraph 1 — Introduction**
Identify yourself: name, ID, program, semester/year. State the purpose of the letter in
one sentence.

**Paragraph 2 — Situation / Background**
Explain the circumstances that led to this request. Be factual, specific, and respectful.
If there is a valid reason (illness, financial difficulty, administrative error, clash),
state it clearly. If documents are attached, mention them here.

**Paragraph 3 — Impact / Urgency (if applicable)**
Briefly explain what will happen if the request is not granted — missed exam, inability
to register, academic setback. Keep this factual, not dramatic.

**Paragraph 4 — Formal Request**
One sentence: "I, therefore, respectfully request you to kindly [specific action]."

**Closing line** (always):
"I shall be highly obliged for your kind consideration."

---

## Writing Standards

- **Tone**: Formal, humble, respectful — never casual, never aggressive
- **Language**: Clear, simple, grammatically correct English
- **Length**: 200–350 words for most applications; never exceed one page
- **Tense**: Present and past only (no speculative future tense in the request)
- **Salutation**: Always "Respected Sir/Madam" unless a specific name is given
- **Avoid**: Slang, abbreviations, emotional language, threats, or blame
- **Phrases to use**:
  - "I humbly request..."
  - "I shall be highly obliged..."
  - "Kindly consider my application..."
  - "I am enclosing / I am attaching..."
  - "Due to unavoidable circumstances..."
- **Phrases to avoid**:
  - "I want you to..."
  - "You should..."
  - "It is your duty..."
  - "I need this ASAP"

---

## Step 4 — Output Format

### Default: In-chat plain text
Present the formatted application directly in the conversation with clear visual spacing.

### .docx output
Create a Word document when the user asks for a file, mentions printing, or needs to submit
a hard copy. Read `/mnt/skills/public/docx/SKILL.md` first if producing .docx.

Use:
- Font: Times New Roman 12pt
- Margins: 1 inch (1440 DXA) all sides
- Line spacing: 1.5
- Page size: A4

---

## Step 5 — Offer Follow-up

After presenting the application, offer:
1. **Urdu translation** if needed
2. **Shorter version** if there is a word limit
3. **Adjustment** if they want a stricter or softer tone
4. **Multiple copies** tailored to different recipients (e.g., HOD + Registrar)

---

## Custom Formats (User-Uploaded Templates)

When a user uploads their university's official application format or form:
1. Read the uploaded document carefully
2. Identify all required fields, headings, and sections
3. Fill them in using the student's provided information
4. Preserve the exact structure and field names of the template
5. Do not add sections that the template doesn't include

The uploaded format always overrides the default structure above.
