from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.legal_right import LegalRight

PAGE_SIZE = 50


async def list_legal_rights(
    db: AsyncSession,
    category: str | None = None,
    page: int = 1,
) -> list[LegalRight]:
    q = select(LegalRight).where(LegalRight.published.is_(True))
    if category:
        q = q.where(LegalRight.category == category)
    q = q.order_by(LegalRight.sort_order, LegalRight.title_en)
    q = q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    return list(result.scalars().all())


# ── Curated corpus of Bangladesh-law explainers (bilingual EN + BN) ──────────
# illustration keys map to SVG scenes in the student app (apps/student/src/screens.jsx):
#   shield · lock · gavel · building · heart · scale · book · eye · route · doc
LEGAL_RIGHTS_CORPUS: list[dict] = [
    {
        "category": "personal_safety",
        "title_en": "Right against harassment in public spaces",
        "title_bn": "প্রকাশ্য স্থানে হয়রানির বিরুদ্ধে অধিকার",
        "summary_en": "Insulting the modesty of a woman by word, gesture or act is a criminal offence.",
        "summary_bn": "কথা, অঙ্গভঙ্গি বা কাজের মাধ্যমে কোনো নারীর শ্লীলতাহানি একটি ফৌজদারি অপরাধ।",
        "full_text_en": "Any word, gesture, or act intended to insult the modesty of a woman is punishable with imprisonment up to one year, or fine, or both. This includes 'eve-teasing', stalking and unwanted advances in public.",
        "full_text_bn": "কোনো নারীর শ্লীলতাহানির উদ্দেশ্যে করা যেকোনো শব্দ, অঙ্গভঙ্গি বা কাজ এক বছর পর্যন্ত কারাদণ্ড, অথবা জরিমানা, অথবা উভয় দণ্ডে দণ্ডনীয়। ইভ-টিজিং, অনুসরণ ও অনাকাঙ্ক্ষিত আচরণ এর অন্তর্ভুক্ত।",
        "penalty_en": "Up to 1 year imprisonment or fine",
        "penalty_bn": "১ বছর পর্যন্ত কারাদণ্ড বা জরিমানা",
        "where_to_invoke_en": "File a GD or complaint at the nearest thana, or call the National Helpline 999.",
        "where_to_invoke_bn": "নিকটস্থ থানায় জিডি বা অভিযোগ করুন, অথবা জাতীয় হেল্পলাইন ৯৯৯-এ কল করুন।",
        "citation": "Penal Code 1860 · §509",
        "steps": [
            {"en": "Note the time, place and any witnesses.", "bn": "সময়, স্থান ও সাক্ষীদের তথ্য লিখে রাখুন।"},
            {"en": "Record evidence (photo, video) safely if possible.", "bn": "সম্ভব হলে নিরাপদে প্রমাণ (ছবি, ভিডিও) সংরক্ষণ করুন।"},
            {"en": "File a GD at the local thana or call 999.", "bn": "স্থানীয় থানায় জিডি করুন অথবা ৯৯৯-এ কল করুন।"},
        ],
        "illustration": "shield", "accent": "#C44536", "sort_order": 10,
    },
    {
        "category": "cyber",
        "title_en": "Right to lodge a cyber-harassment complaint",
        "title_bn": "সাইবার হয়রানির অভিযোগ করার অধিকার",
        "summary_en": "Targeted online harassment is a cognizable offence under the Cyber Security Act.",
        "summary_bn": "লক্ষ্যবস্তু করে অনলাইন হয়রানি সাইবার নিরাপত্তা আইনে আমলযোগ্য অপরাধ।",
        "full_text_en": "Online harassment, defamation, identity theft and publishing private images without consent are punishable offences. You may file at the Cyber Police Centre or any thana, which forwards it to the Cyber Tribunal.",
        "full_text_bn": "অনলাইনে হয়রানি, মানহানি, পরিচয় চুরি এবং সম্মতি ছাড়া ব্যক্তিগত ছবি প্রকাশ শাস্তিযোগ্য অপরাধ। আপনি সাইবার পুলিশ সেন্টার বা যেকোনো থানায় অভিযোগ করতে পারেন, যা সাইবার ট্রাইব্যুনালে পাঠানো হয়।",
        "penalty_en": "Varies by offence — fines and imprisonment",
        "penalty_bn": "অপরাধভেদে — জরিমানা ও কারাদণ্ড",
        "where_to_invoke_en": "CID Cyber Police Centre, any thana, or report via the 'Cyber Support for Women' Facebook page / 999.",
        "where_to_invoke_bn": "সিআইডি সাইবার পুলিশ সেন্টার, যেকোনো থানা, অথবা 'Cyber Support for Women' পেজ / ৯৯৯-এ জানান।",
        "citation": "Cyber Security Act 2023 · §25",
        "steps": [
            {"en": "Take screenshots with URLs and timestamps.", "bn": "ইউআরএল ও সময়সহ স্ক্রিনশট নিন।"},
            {"en": "Do not delete the offending messages.", "bn": "আপত্তিকর বার্তাগুলো মুছে ফেলবেন না।"},
            {"en": "Report to the Cyber Police Centre or any thana.", "bn": "সাইবার পুলিশ সেন্টার বা যেকোনো থানায় জানান।"},
        ],
        "illustration": "lock", "accent": "#3A5A8C", "sort_order": 20,
    },
    {
        "category": "custody",
        "title_en": "Right to inform a relative on arrest",
        "title_bn": "গ্রেপ্তারে আত্মীয়কে জানানোর অধিকার",
        "summary_en": "On arrest you must be told the grounds, allowed a lawyer, and produced before a magistrate within 24 hours.",
        "summary_bn": "গ্রেপ্তারে আপনাকে কারণ জানাতে হবে, আইনজীবী রাখার সুযোগ দিতে হবে এবং ২৪ ঘণ্টার মধ্যে ম্যাজিস্ট্রেটের সামনে হাজির করতে হবে।",
        "full_text_en": "On arrest, you must be informed of the grounds, allowed to consult a lawyer of your choice, and produced before a magistrate within twenty-four hours (excluding travel time). A relative or friend must be informed of the arrest.",
        "full_text_bn": "গ্রেপ্তারের সময় আপনাকে অবশ্যই কারণ জানাতে হবে, নিজের পছন্দের আইনজীবীর সঙ্গে পরামর্শের সুযোগ দিতে হবে এবং (যাতায়াতের সময় বাদে) চব্বিশ ঘণ্টার মধ্যে ম্যাজিস্ট্রেটের সামনে হাজির করতে হবে। গ্রেপ্তারের বিষয়ে একজন আত্মীয় বা বন্ধুকে জানাতে হবে।",
        "penalty_en": "Violation is grounds for relief from the High Court",
        "penalty_bn": "লঙ্ঘন হাইকোর্টে প্রতিকার পাওয়ার ভিত্তি",
        "where_to_invoke_en": "Insist on these rights at arrest; a lawyer can file a habeas corpus petition if denied.",
        "where_to_invoke_bn": "গ্রেপ্তারের সময় এই অধিকারগুলো দাবি করুন; অস্বীকার করা হলে আইনজীবী হেবিয়াস কর্পাস রিট করতে পারেন।",
        "citation": "CrPC §60A · Constitution Art. 33",
        "steps": [
            {"en": "Ask for the reason for arrest in writing.", "bn": "গ্রেপ্তারের কারণ লিখিতভাবে জানতে চান।"},
            {"en": "Request to call a lawyer and a relative.", "bn": "একজন আইনজীবী ও আত্মীয়কে ফোন করার অনুরোধ করুন।"},
            {"en": "Confirm you are produced before a magistrate within 24h.", "bn": "২৪ ঘণ্টার মধ্যে ম্যাজিস্ট্রেটের সামনে হাজির করা নিশ্চিত করুন।"},
        ],
        "illustration": "gavel", "accent": "#7A5230", "sort_order": 30,
    },
    {
        "category": "workplace",
        "title_en": "Right to a safe workplace",
        "title_bn": "নিরাপদ কর্মস্থলের অধিকার",
        "summary_en": "Every workplace and institution must have a sexual-harassment complaint committee chaired by a woman.",
        "summary_bn": "প্রতিটি কর্মস্থল ও প্রতিষ্ঠানে নারীর নেতৃত্বে যৌন হয়রানি অভিযোগ কমিটি থাকতে হবে।",
        "full_text_en": "Following the 2009 High Court directive, every workplace, including educational institutions, must establish a complaint committee for sexual harassment, with a majority of women members and chaired by a woman. The directive has the force of law until legislation is passed.",
        "full_text_bn": "২০০৯ সালের হাইকোর্টের নির্দেশনা অনুযায়ী, শিক্ষাপ্রতিষ্ঠানসহ প্রতিটি কর্মস্থলে যৌন হয়রানি প্রতিরোধে একটি অভিযোগ কমিটি গঠন করতে হবে, যার অধিকাংশ সদস্য নারী এবং সভাপতি একজন নারী হবেন। আইন প্রণীত না হওয়া পর্যন্ত এই নির্দেশনা আইনের মর্যাদা রাখে।",
        "penalty_en": "Non-compliance is contempt of the High Court directive",
        "penalty_bn": "অমান্য করা হাইকোর্টের নির্দেশনা অবমাননা",
        "where_to_invoke_en": "Complain to your institution's committee; escalate to the Mahila Parishad or a writ if ignored.",
        "where_to_invoke_bn": "আপনার প্রতিষ্ঠানের কমিটিতে অভিযোগ করুন; উপেক্ষিত হলে মহিলা পরিষদ বা রিটে যান।",
        "citation": "High Court Directive 2009 (BNWLA case)",
        "steps": [
            {"en": "Submit a written complaint to the committee.", "bn": "কমিটির কাছে লিখিত অভিযোগ জমা দিন।"},
            {"en": "Keep a copy and note the date received.", "bn": "একটি অনুলিপি রাখুন ও গ্রহণের তারিখ লিখুন।"},
            {"en": "Escalate to a writ petition if no action follows.", "bn": "ব্যবস্থা না নিলে রিট পিটিশনে যান।"},
        ],
        "illustration": "building", "accent": "#4A6B5C", "sort_order": 40,
    },
    {
        "category": "domestic",
        "title_en": "Right to seek a protection order",
        "title_bn": "সুরক্ষা আদেশ চাওয়ার অধিকার",
        "summary_en": "Victims of domestic violence can apply for residence, protection and compensation orders.",
        "summary_bn": "পারিবারিক সহিংসতার শিকার ব্যক্তি বসবাস, সুরক্ষা ও ক্ষতিপূরণ আদেশের জন্য আবেদন করতে পারেন।",
        "full_text_en": "Victims of domestic violence — physical, psychological, sexual or economic abuse — may apply to a Court of Magistrate for a residence order, protection order, or compensation. The court can act within a limited time and order police protection.",
        "full_text_bn": "পারিবারিক সহিংসতার শিকার — শারীরিক, মানসিক, যৌন বা অর্থনৈতিক নির্যাতন — ব্যক্তি ম্যাজিস্ট্রেট আদালতে বসবাস আদেশ, সুরক্ষা আদেশ বা ক্ষতিপূরণের জন্য আবেদন করতে পারেন। আদালত নির্দিষ্ট সময়ের মধ্যে ব্যবস্থা নিতে ও পুলিশি সুরক্ষার আদেশ দিতে পারেন।",
        "penalty_en": "Breach of a protection order is punishable with jail and fine",
        "penalty_bn": "সুরক্ষা আদেশ লঙ্ঘন কারাদণ্ড ও জরিমানায় দণ্ডনীয়",
        "where_to_invoke_en": "Apply through a Court of Magistrate; an enforcement officer or NGO can assist.",
        "where_to_invoke_bn": "ম্যাজিস্ট্রেট আদালতে আবেদন করুন; একজন প্রয়োগকারী কর্মকর্তা বা এনজিও সহায়তা করতে পারে।",
        "citation": "DV (Prevention & Protection) Act 2010",
        "steps": [
            {"en": "Seek medical care and keep records.", "bn": "চিকিৎসা নিন ও নথি সংরক্ষণ করুন।"},
            {"en": "Contact an enforcement officer or NGO.", "bn": "একজন প্রয়োগকারী কর্মকর্তা বা এনজিওর সঙ্গে যোগাযোগ করুন।"},
            {"en": "Apply to a Magistrate for a protection order.", "bn": "সুরক্ষা আদেশের জন্য ম্যাজিস্ট্রেটের কাছে আবেদন করুন।"},
        ],
        "illustration": "heart", "accent": "#B0436A", "sort_order": 50,
    },
    {
        "category": "privacy",
        "title_en": "Right to privacy and consent",
        "title_bn": "গোপনীয়তা ও সম্মতির অধিকার",
        "summary_en": "Privacy of correspondence and communication is a constitutional right.",
        "summary_bn": "চিঠিপত্র ও যোগাযোগের গোপনীয়তা একটি সাংবিধানিক অধিকার।",
        "full_text_en": "Every citizen has the right to privacy of correspondence and communication. Surveillance, interception or sharing of personal data without due process or consent is unconstitutional.",
        "full_text_bn": "প্রত্যেক নাগরিকের চিঠিপত্র ও যোগাযোগের গোপনীয়তার অধিকার রয়েছে। যথাযথ আইনি প্রক্রিয়া বা সম্মতি ছাড়া নজরদারি, আড়িপাতা বা ব্যক্তিগত তথ্য শেয়ার করা অসাংবিধানিক।",
        "penalty_en": "Remediable through writ jurisdiction of the High Court",
        "penalty_bn": "হাইকোর্টের রিট এখতিয়ারে প্রতিকারযোগ্য",
        "where_to_invoke_en": "Challenge unlawful surveillance via a writ petition in the High Court Division.",
        "where_to_invoke_bn": "বেআইনি নজরদারির বিরুদ্ধে হাইকোর্ট বিভাগে রিট পিটিশন করুন।",
        "citation": "Constitution Art. 43",
        "steps": [
            {"en": "Document the privacy violation.", "bn": "গোপনীয়তা লঙ্ঘনের প্রমাণ সংরক্ষণ করুন।"},
            {"en": "Consult a lawyer about a writ petition.", "bn": "রিট পিটিশন নিয়ে একজন আইনজীবীর পরামর্শ নিন।"},
        ],
        "illustration": "eye", "accent": "#5B6770", "sort_order": 60,
    },
    {
        "category": "consumer",
        "title_en": "Right to fair goods and services",
        "title_bn": "ন্যায্য পণ্য ও সেবার অধিকার",
        "summary_en": "Selling adulterated, fake or overpriced goods is a punishable consumer offence.",
        "summary_bn": "ভেজাল, নকল বা অতিরিক্ত দামে পণ্য বিক্রি শাস্তিযোগ্য ভোক্তা অপরাধ।",
        "full_text_en": "Selling adulterated or date-expired goods, charging above the listed price, or giving less than the promised weight are offences. Consumers can complain to the Directorate of National Consumer Rights Protection and receive 25% of the imposed fine.",
        "full_text_bn": "ভেজাল বা মেয়াদোত্তীর্ণ পণ্য বিক্রি, তালিকাভুক্ত দামের বেশি নেওয়া, বা প্রতিশ্রুত ওজনের কম দেওয়া অপরাধ। ভোক্তারা জাতীয় ভোক্তা-অধিকার সংরক্ষণ অধিদপ্তরে অভিযোগ করতে পারেন এবং আরোপিত জরিমানার ২৫% পান।",
        "penalty_en": "Fine and/or imprisonment; complainant gets 25% of fine",
        "penalty_bn": "জরিমানা ও/অথবা কারাদণ্ড; অভিযোগকারী জরিমানার ২৫% পান",
        "where_to_invoke_en": "Complain to the DNCRP within 30 days, in person or via their hotline 16121.",
        "where_to_invoke_bn": "৩০ দিনের মধ্যে ডিএনসিআরপি-তে সরাসরি বা হটলাইন ১৬১২১-এ অভিযোগ করুন।",
        "citation": "Consumer Rights Protection Act 2009",
        "steps": [
            {"en": "Keep the receipt and the product.", "bn": "রসিদ ও পণ্যটি সংরক্ষণ করুন।"},
            {"en": "File a written complaint within 30 days.", "bn": "৩০ দিনের মধ্যে লিখিত অভিযোগ করুন।"},
            {"en": "Call the DNCRP hotline 16121.", "bn": "ডিএনসিআরপি হটলাইন ১৬১২১-এ কল করুন।"},
        ],
        "illustration": "scale", "accent": "#A8762B", "sort_order": 70,
    },
    {
        "category": "rti",
        "title_en": "Right to information from authorities",
        "title_bn": "কর্তৃপক্ষের কাছ থেকে তথ্যের অধিকার",
        "summary_en": "Citizens can request information held by public and many private bodies.",
        "summary_bn": "নাগরিকরা সরকারি ও অনেক বেসরকারি সংস্থার কাছে থাকা তথ্য চাইতে পারেন।",
        "full_text_en": "Any citizen can request information from public authorities, NGOs and bodies funded by the government. The designated officer must respond within 20 working days (or 30 if multiple offices are involved). Refusal can be appealed to the Information Commission.",
        "full_text_bn": "যেকোনো নাগরিক সরকারি কর্তৃপক্ষ, এনজিও ও সরকারি অর্থে পরিচালিত সংস্থার কাছে তথ্য চাইতে পারেন। নির্ধারিত কর্মকর্তাকে ২০ কার্যদিবসের মধ্যে (একাধিক দপ্তর জড়িত থাকলে ৩০ দিন) উত্তর দিতে হবে। প্রত্যাখ্যানের বিরুদ্ধে তথ্য কমিশনে আপিল করা যায়।",
        "penalty_en": "Officer fined for delay or wrongful refusal",
        "penalty_bn": "বিলম্ব বা অন্যায্য প্রত্যাখ্যানে কর্মকর্তার জরিমানা",
        "where_to_invoke_en": "Submit the prescribed form to the designated officer; appeal to the Information Commission.",
        "where_to_invoke_bn": "নির্ধারিত ফরম দায়িত্বপ্রাপ্ত কর্মকর্তার কাছে জমা দিন; তথ্য কমিশনে আপিল করুন।",
        "citation": "Right to Information Act 2009",
        "steps": [
            {"en": "Fill the prescribed RTI request form.", "bn": "নির্ধারিত আরটিআই আবেদন ফরম পূরণ করুন।"},
            {"en": "Submit to the designated information officer.", "bn": "দায়িত্বপ্রাপ্ত তথ্য কর্মকর্তার কাছে জমা দিন।"},
            {"en": "Appeal to the Information Commission if refused.", "bn": "প্রত্যাখ্যাত হলে তথ্য কমিশনে আপিল করুন।"},
        ],
        "illustration": "book", "accent": "#3F7E73", "sort_order": 80,
    },
    {
        "category": "dowry",
        "title_en": "Right against dowry demands",
        "title_bn": "যৌতুক দাবির বিরুদ্ধে অধিকার",
        "summary_en": "Demanding, giving or taking dowry is a criminal offence.",
        "summary_bn": "যৌতুক দাবি, দেওয়া বা নেওয়া একটি ফৌজদারি অপরাধ।",
        "full_text_en": "Demanding, giving, or taking dowry directly or indirectly in connection with a marriage is punishable. Dowry-related violence carries enhanced penalties, including life imprisonment in severe cases.",
        "full_text_bn": "বিবাহ সম্পর্কিত প্রত্যক্ষ বা পরোক্ষভাবে যৌতুক দাবি, দেওয়া বা নেওয়া শাস্তিযোগ্য। যৌতুকজনিত সহিংসতায় গুরুতর ক্ষেত্রে যাবজ্জীবন কারাদণ্ডসহ বর্ধিত শাস্তি রয়েছে।",
        "penalty_en": "1–5 years imprisonment and fine; more for violence",
        "penalty_bn": "১–৫ বছর কারাদণ্ড ও জরিমানা; সহিংসতায় আরও বেশি",
        "where_to_invoke_en": "File a case at the thana or the Nari-o-Shishu Nirjatan Daman Tribunal.",
        "where_to_invoke_bn": "থানায় বা নারী ও শিশু নির্যাতন দমন ট্রাইব্যুনালে মামলা করুন।",
        "citation": "Dowry Prohibition Act 2018",
        "steps": [
            {"en": "Preserve messages or witnesses of the demand.", "bn": "দাবির বার্তা বা সাক্ষী সংরক্ষণ করুন।"},
            {"en": "File a case at the thana or women's tribunal.", "bn": "থানায় বা নারী ট্রাইব্যুনালে মামলা করুন।"},
        ],
        "illustration": "heart", "accent": "#B0436A", "sort_order": 90,
    },
    {
        "category": "child_marriage",
        "title_en": "Right against child marriage",
        "title_bn": "বাল্যবিবাহের বিরুদ্ধে অধিকার",
        "summary_en": "Marriage below 18 (women) and 21 (men) is prohibited and punishable.",
        "summary_bn": "নারীর ১৮ ও পুরুষের ২১ বছরের নিচে বিবাহ নিষিদ্ধ ও শাস্তিযোগ্য।",
        "full_text_en": "Marriage of a girl under 18 or a boy under 21 is prohibited. Adults who arrange, conduct or solemnize a child marriage — including parents and the marriage registrar — are liable to punishment.",
        "full_text_bn": "১৮ বছরের নিচে কোনো মেয়ে বা ২১ বছরের নিচে কোনো ছেলের বিবাহ নিষিদ্ধ। বাল্যবিবাহ আয়োজন, সম্পাদন বা নিবন্ধনকারী প্রাপ্তবয়স্করা — মা-বাবা ও কাজীসহ — শাস্তির আওতায় পড়েন।",
        "penalty_en": "Imprisonment up to 2 years and/or fine",
        "penalty_bn": "২ বছর পর্যন্ত কারাদণ্ড ও/অথবা জরিমানা",
        "where_to_invoke_en": "Report to the UNO, local administration, the thana, or call 999 / 1098 (child helpline).",
        "where_to_invoke_bn": "ইউএনও, স্থানীয় প্রশাসন, থানায় জানান অথবা ৯৯৯ / ১০৯৮ (শিশু হেল্পলাইন)-এ কল করুন।",
        "citation": "Child Marriage Restraint Act 2017",
        "steps": [
            {"en": "Report early to the UNO or local administration.", "bn": "দ্রুত ইউএনও বা স্থানীয় প্রশাসনকে জানান।"},
            {"en": "Call the child helpline 1098 or 999.", "bn": "শিশু হেল্পলাইন ১০৯৮ বা ৯৯৯-এ কল করুন।"},
        ],
        "illustration": "shield", "accent": "#C44536", "sort_order": 100,
    },
    {
        "category": "road",
        "title_en": "Right to compensation for road accidents",
        "title_bn": "সড়ক দুর্ঘটনায় ক্ষতিপূরণের অধিকার",
        "summary_en": "Victims of reckless driving can claim compensation and the driver faces criminal liability.",
        "summary_bn": "বেপরোয়া চালনায় ক্ষতিগ্রস্তরা ক্ষতিপূরণ দাবি করতে পারেন এবং চালক ফৌজদারি দায়ে পড়েন।",
        "full_text_en": "Reckless or negligent driving causing death or injury is a criminal offence with significant penalties. Victims and families are entitled to claim compensation through the prescribed process.",
        "full_text_bn": "বেপরোয়া বা অবহেলাজনিত চালনায় মৃত্যু বা আঘাত একটি ফৌজদারি অপরাধ এবং উল্লেখযোগ্য শাস্তিযোগ্য। ক্ষতিগ্রস্ত ও পরিবার নির্ধারিত প্রক্রিয়ায় ক্ষতিপূরণ দাবি করার অধিকারী।",
        "penalty_en": "Up to 5 years imprisonment; more for intent",
        "penalty_bn": "৫ বছর পর্যন্ত কারাদণ্ড; ইচ্ছাকৃত হলে আরও বেশি",
        "where_to_invoke_en": "File an FIR at the thana; the case goes to the relevant court for trial and compensation.",
        "where_to_invoke_bn": "থানায় এফআইআর করুন; মামলা বিচার ও ক্ষতিপূরণের জন্য সংশ্লিষ্ট আদালতে যায়।",
        "citation": "Road Transport Act 2018",
        "steps": [
            {"en": "Note the vehicle number and gather witnesses.", "bn": "গাড়ির নম্বর লিখুন ও সাক্ষী সংগ্রহ করুন।"},
            {"en": "Get a medical/post-mortem report.", "bn": "চিকিৎসা/ময়নাতদন্ত প্রতিবেদন নিন।"},
            {"en": "File an FIR at the thana.", "bn": "থানায় এফআইআর করুন।"},
        ],
        "illustration": "route", "accent": "#7A5230", "sort_order": 110,
    },
    {
        "category": "labor",
        "title_en": "Right to fair wages and safe work",
        "title_bn": "ন্যায্য মজুরি ও নিরাপদ কাজের অধিকার",
        "summary_en": "Workers are entitled to timely wages, leave, and a safe workplace.",
        "summary_bn": "শ্রমিকরা সময়মতো মজুরি, ছুটি ও নিরাপদ কর্মস্থলের অধিকারী।",
        "full_text_en": "Workers have the right to wages paid on time, weekly holidays, paid leave, maternity benefit, compensation for workplace injury, and a safe working environment. Unfair dismissal can be challenged before the Labour Court.",
        "full_text_bn": "শ্রমিকরা সময়মতো মজুরি, সাপ্তাহিক ছুটি, সবেতন ছুটি, মাতৃত্বকালীন সুবিধা, কর্মস্থলে আঘাতের ক্ষতিপূরণ এবং নিরাপদ কর্মপরিবেশের অধিকারী। অন্যায্য চাকরিচ্যুতির বিরুদ্ধে শ্রম আদালতে চ্যালেঞ্জ করা যায়।",
        "penalty_en": "Employer liable to fines and back-pay orders",
        "penalty_bn": "নিয়োগকর্তা জরিমানা ও বকেয়া মজুরি আদেশের দায়ে",
        "where_to_invoke_en": "Complain to the Department of Inspection for Factories or file at the Labour Court.",
        "where_to_invoke_bn": "কলকারখানা পরিদর্শন অধিদপ্তরে অভিযোগ করুন বা শ্রম আদালতে মামলা করুন।",
        "citation": "Bangladesh Labour Act 2006",
        "steps": [
            {"en": "Keep your appointment letter and pay records.", "bn": "নিয়োগপত্র ও বেতন নথি সংরক্ষণ করুন।"},
            {"en": "Complain to the factory inspection department.", "bn": "কলকারখানা পরিদর্শন অধিদপ্তরে অভিযোগ করুন।"},
            {"en": "File at the Labour Court if unresolved.", "bn": "সমাধান না হলে শ্রম আদালতে মামলা করুন।"},
        ],
        "illustration": "building", "accent": "#4A6B5C", "sort_order": 120,
    },
    {
        "category": "custody",
        "title_en": "Right to free legal aid",
        "title_bn": "বিনামূল্যে আইনি সহায়তার অধিকার",
        "summary_en": "Those unable to afford a lawyer can get government legal aid.",
        "summary_bn": "যারা আইনজীবীর খরচ বহন করতে অক্ষম তারা সরকারি আইনি সহায়তা পেতে পারেন।",
        "full_text_en": "Financially insolvent people — including those earning below a set threshold, women, children and detainees — are entitled to free legal representation, mediation and case costs through the District Legal Aid Committee.",
        "full_text_bn": "আর্থিকভাবে অসচ্ছল ব্যক্তি — নির্ধারিত আয়ের নিচে থাকা ব্যক্তি, নারী, শিশু ও আটক ব্যক্তিসহ — জেলা আইনি সহায়তা কমিটির মাধ্যমে বিনামূল্যে আইনি প্রতিনিধিত্ব, মধ্যস্থতা ও মামলার খরচ পাওয়ার অধিকারী।",
        "penalty_en": "—",
        "penalty_bn": "—",
        "where_to_invoke_en": "Apply at the District Legal Aid Committee or call the legal-aid hotline 16430.",
        "where_to_invoke_bn": "জেলা আইনি সহায়তা কমিটিতে আবেদন করুন অথবা আইনি সহায়তা হটলাইন ১৬৪৩০-এ কল করুন।",
        "citation": "Legal Aid Services Act 2000",
        "steps": [
            {"en": "Call the legal-aid hotline 16430.", "bn": "আইনি সহায়তা হটলাইন ১৬৪৩০-এ কল করুন।"},
            {"en": "Apply at the District Legal Aid Committee.", "bn": "জেলা আইনি সহায়তা কমিটিতে আবেদন করুন।"},
        ],
        "illustration": "scale", "accent": "#3A5A8C", "sort_order": 130,
    },
]


async def seed_legal_rights(db: AsyncSession) -> int:
    """Idempotent: insert the curated corpus only if the table is empty.
    Returns the number of rows inserted (0 if already seeded)."""
    count = await db.scalar(select(func.count()).select_from(LegalRight))
    if count and count > 0:
        return 0
    for item in LEGAL_RIGHTS_CORPUS:
        db.add(LegalRight(**item))
    await db.commit()
    return len(LEGAL_RIGHTS_CORPUS)
