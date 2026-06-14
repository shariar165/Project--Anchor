// Mock data for Anchor AI admin demo
window.AnchorData = (() => {
  const complaints = [
    {
      id: 'CMP-2026-A4F2', title: 'AC unit in Room 504 has been broken for two weeks',
      category: 'Classroom', categoryIcon: 'door-open', severity: 2, anonymous: false,
      submittedBy: 'Rafiul Hasan', batch: '54-A', dept: 'SWE',
      status: 'Under Review', routing: ['Dept Head'], level: 1,
      submitted: '2026-05-21 09:14', lastAction: '2026-05-22 11:02',
      body: 'The air conditioning unit in Room 504 (Knowledge Tower, 5th floor) has been non-functional since 8 May. Classes in that room run at 33–34°C in the afternoon. I have already mentioned this to the room supervisor twice but no maintenance has been scheduled. Please escalate to facilities.',
      timeline: [
        { t: '2026-05-21 09:14', who: 'Student', what: 'Complaint submitted' },
        { t: '2026-05-21 09:14', who: 'AI Router', what: 'Auto-routed to Department Head (Level 1)' },
        { t: '2026-05-22 11:02', who: 'Dr. Mahbub Alam', what: 'Marked Under Review · note added' },
      ],
      evidence: ['IMG_0421.jpg', 'IMG_0422.jpg'],
      notes: 'Facilities ticket FAC-9281 raised. Awaiting maintenance window.',
      patternHint: '2 other classroom-cooling complaints filed in Knowledge Tower this month.',
    },
    {
      id: 'CMP-2026-A4F3', title: 'Favoritism in section assignment for SWE-405 lab',
      category: 'Teacher Conduct', categoryIcon: 'user-square', severity: 3, anonymous: true,
      submittedBy: 'S***** A*****', batch: '53-B', dept: 'SWE',
      status: 'Escalated', routing: ['Dept Head', 'Dean'], level: 2,
      submitted: '2026-05-20 16:42', lastAction: '2026-05-23 09:15',
      body: 'Three students in our section appear to receive preferential lab partner assignment and extra makeup-quiz opportunities from the SWE-405 lab instructor. Other students raising this informally have been dismissed. I am reporting anonymously because retaliation is a real concern.',
      timeline: [
        { t: '2026-05-20 16:42', who: 'Anonymous', what: 'Complaint submitted (anonymous)' },
        { t: '2026-05-20 16:42', who: 'AI Router', what: 'Rank-3 protection applied · routed to Dean' },
        { t: '2026-05-22 14:01', who: 'Dr. Mahbub Alam', what: 'Reviewed · escalated to Dean' },
        { t: '2026-05-23 09:15', who: 'Dr. Tahmina Karim', what: 'Acknowledged · review scheduled' },
      ],
      evidence: [],
      notes: 'Cross-check with anonymous culture reports for SWE-405. Pattern likely.',
      patternHint: '4 anonymous reports in the past 6 weeks mention the same lab instructor.',
    },
    {
      id: 'CMP-2026-A4F4', title: 'Hostel curfew enforcement is inconsistent between halls',
      category: 'Hostel', categoryIcon: 'bed', severity: 1, anonymous: false,
      submittedBy: 'Naima Sultana', batch: '55-A', dept: 'CSE',
      status: 'Submitted', routing: ['Provost'], level: 1,
      submitted: '2026-05-23 22:18', lastAction: '2026-05-23 22:18',
      body: 'Female Hall-2 enforces a 9:30 PM curfew strictly while Female Hall-1 has effectively pushed back to 10:30. Same university, same handbook. Please align policy.',
      timeline: [
        { t: '2026-05-23 22:18', who: 'Student', what: 'Complaint submitted' },
      ],
      evidence: [],
      notes: '',
      patternHint: null,
    },
    {
      id: 'CMP-2026-A4F5', title: 'Projector in Lab 308 fails every Sunday morning',
      category: 'Classroom', categoryIcon: 'door-open', severity: 1, anonymous: false,
      submittedBy: 'Tanjir Ahmed', batch: '54-A', dept: 'SWE',
      status: 'Resolved', routing: ['Dept Head'], level: 1,
      submitted: '2026-05-12 08:30', lastAction: '2026-05-18 16:40',
      body: 'Projector in Lab 308 fails to start the first lecture every Sunday. Tech team typically swaps the HDMI cable and it works for the rest of the week.',
      timeline: [
        { t: '2026-05-12 08:30', who: 'Student', what: 'Complaint submitted' },
        { t: '2026-05-13 10:00', who: 'Dr. Mahbub Alam', what: 'Marked Under Review' },
        { t: '2026-05-18 16:40', who: 'Facilities', what: 'Replaced projector unit · Resolved' },
      ],
      evidence: ['IMG_0399.jpg'],
      notes: 'Replacement BenQ MW560 installed.',
      patternHint: null,
    },
    {
      id: 'CMP-2026-A4F6', title: 'Repeated humiliation by SWE-301 instructor during viva',
      category: 'Teacher Conduct', categoryIcon: 'user-square', severity: 3, anonymous: true,
      submittedBy: 'F***** R*****', batch: '54-B', dept: 'SWE',
      status: 'Under Review', routing: ['Dept Head', 'Dean'], level: 2,
      submitted: '2026-05-19 14:55', lastAction: '2026-05-22 17:30',
      body: 'During the SWE-301 mid-term viva, the instructor mocked two students for their accent in front of the panel. This has happened in prior semesters as well. Multiple students have witnessed it.',
      timeline: [
        { t: '2026-05-19 14:55', who: 'Anonymous', what: 'Complaint submitted' },
        { t: '2026-05-22 17:30', who: 'Dr. Tahmina Karim', what: 'Marked Under Review · witnesses contacted' },
      ],
      evidence: [],
      notes: '',
      patternHint: '2 corroborating witness statements collected via anonymous channel.',
    },
    {
      id: 'CMP-2026-A4F7', title: 'Library extension hours during finals — proposal',
      category: 'Academic', categoryIcon: 'graduation-cap', severity: 1, anonymous: false,
      submittedBy: 'Md. Sajid Karim', batch: '53-A', dept: 'EEE',
      status: 'Submitted', routing: ['Dept Head'], level: 1,
      submitted: '2026-05-23 11:00', lastAction: '2026-05-23 11:00',
      body: 'Requesting the central library extend hours to 1 AM during finals week (June 8–15). This was done in Spring 2024 and was effective.',
      timeline: [{ t: '2026-05-23 11:00', who: 'Student', what: 'Complaint submitted' }],
      evidence: [],
      notes: '',
      patternHint: null,
    },
    {
      id: 'CMP-2026-A4F8', title: 'Lift in Knowledge Tower stuck on 7th floor',
      category: 'Department', categoryIcon: 'building-2', severity: 2, anonymous: false,
      submittedBy: 'Sumaiya Akter', batch: '55-B', dept: 'SWE',
      status: 'Under Review', routing: ['Dept Head'], level: 1,
      submitted: '2026-05-22 08:00', lastAction: '2026-05-22 09:00',
      body: 'The east lift has been stuck on the 7th floor for two days. Students with mobility issues cannot attend classes on upper floors.',
      timeline: [
        { t: '2026-05-22 08:00', who: 'Student', what: 'Complaint submitted' },
        { t: '2026-05-22 09:00', who: 'Dr. Mahbub Alam', what: 'Marked Under Review · facilities notified' },
      ],
      evidence: ['IMG_0501.jpg'],
      notes: '',
      patternHint: null,
    },
    {
      id: 'CMP-2026-A4F9', title: 'Grade dispute — SWE-405 Section A midterm',
      category: 'Academic', categoryIcon: 'graduation-cap', severity: 2, anonymous: false,
      submittedBy: 'Ariful Islam', batch: '54-A', dept: 'SWE',
      status: 'Rejected', routing: ['Dept Head'], level: 1,
      submitted: '2026-05-15 12:00', lastAction: '2026-05-17 10:00',
      body: 'My midterm grade was reduced from B+ to B without explanation. I have requested review twice from the instructor.',
      timeline: [
        { t: '2026-05-15 12:00', who: 'Student', what: 'Complaint submitted' },
        { t: '2026-05-17 10:00', who: 'Dr. Mahbub Alam', what: 'Rejected — grade reflects rubric correctly, full breakdown shared.' },
      ],
      evidence: ['rubric.pdf'],
      notes: 'Rubric reviewed with student in office hours.',
      patternHint: null,
    },
  ];

  const alerts = [
    { id: 'ALR-2026-7C12', status: 'Active', location: 'Knowledge Tower · East stairwell, 3rd floor', distance: '120m from Proctor Office', elapsed: '00:04:12', kind: 'Personal safety', triggeredAt: '2026-05-24 21:14' },
    { id: 'ALR-2026-7C10', status: 'Active', location: 'Female Hall 2 · Block C corridor', distance: '480m from Proctor Office', elapsed: '00:11:47', kind: 'Personal safety', triggeredAt: '2026-05-24 21:07' },
    { id: 'ALR-2026-7B92', status: 'Resolved', location: 'Cafeteria Block A', distance: '210m', elapsed: '—', kind: 'Medical', triggeredAt: '2026-05-22 13:02' },
    { id: 'ALR-2026-7B41', status: 'False Alarm', location: 'Library 2F', distance: '90m', elapsed: '—', kind: 'Personal safety', triggeredAt: '2026-05-19 19:55' },
    { id: 'ALR-2026-7A88', status: 'Resolved', location: 'Parking Lot D', distance: '610m', elapsed: '—', kind: 'Theft', triggeredAt: '2026-05-15 08:14' },
  ];

  const tenants = [
    { id: 'diu', name: 'Daffodil International University', domain: '@diu.edu.bd', status: 'Active', users: 8421, cases: 612, schema: 't_diu_main', namespace: 'ns_diu', onboarded: '2025-09-12', contact: 'Dr. Tahmina Karim' },
    { id: 'buet', name: 'Bangladesh University of Engineering & Technology', domain: '@buet.ac.bd', status: 'Pilot', users: 2104, cases: 287, schema: 't_buet_pilot', namespace: 'ns_buet', onboarded: '2026-02-04', contact: 'Prof. Anwar Hossain' },
    { id: 'du', name: 'University of Dhaka', domain: '@du.ac.bd', status: 'Active', users: 1820, cases: 244, schema: 't_du_main', namespace: 'ns_du', onboarded: '2025-11-08', contact: 'Dr. Shamima Rahman' },
    { id: 'nsu', name: 'North South University', domain: '@northsouth.edu', status: 'Suspended', users: 502, cases: 60, schema: 't_nsu_main', namespace: 'ns_nsu', onboarded: '2025-12-20', contact: 'Dr. Imran Chowdhury' },
  ];

  const audit = [
    { t: '2026-05-24 21:18', actor: 'admin_a3f9 (Proctor)', action: 'ALERT_ACKNOWLEDGED', target: 'ALR-2026-7C12', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
    { t: '2026-05-24 19:02', actor: 'admin_d12c (Dean)', action: 'COMPLAINT_ESCALATED', target: 'CMP-2026-A4F3', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
    { t: '2026-05-24 17:30', actor: 'admin_e09a (Dept Head)', action: 'COMPLAINT_STATUS_CHANGE', target: 'CMP-2026-A4F2', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
    { t: '2026-05-24 15:11', actor: 'admin_b220 (IT Admin)', action: 'NOTICE_PUBLISHED', target: 'NTC-2026-0114', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
    { t: '2026-05-24 14:42', actor: 'super_z01 (AiVion)', action: 'ANONYMOUS_DEANONYMIZE_REQUEST', target: 'CMP-2026-A4F3', tenant: 'diu', ip: '103.41.•.•', outcome: 'Pending 2nd approval' },
    { t: '2026-05-24 13:00', actor: 'admin_p41a (Provost)', action: 'COMPLAINT_VIEW', target: 'CMP-2026-A4F4', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
    { t: '2026-05-24 11:28', actor: 'super_z01 (AiVion)', action: 'TENANT_CONFIG_UPDATED', target: 'tenant:buet', tenant: 'buet', ip: '103.41.•.•', outcome: 'OK' },
    { t: '2026-05-24 09:15', actor: 'admin_e09a (Dept Head)', action: 'LOGIN', target: '—', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
    { t: '2026-05-23 22:11', actor: 'admin_x77 (Dean)', action: 'VERIFICATION_POST_REMOVED', target: 'VP-2026-0089', tenant: 'du', ip: '202.84.•.•', outcome: 'OK' },
    { t: '2026-05-23 18:00', actor: 'super_z02 (AiVion)', action: 'DMS_CHECK', target: 'service:dms', tenant: '—', ip: '103.41.•.•', outcome: 'OK' },
    { t: '2026-05-23 12:44', actor: 'admin_e09a (Dept Head)', action: 'COMPLAINT_REJECTED', target: 'CMP-2026-A4F9', tenant: 'diu', ip: '203.81.•.•', outcome: 'OK' },
  ];

  const deanonRequests = [
    { id: 'DAR-2026-0012', case: 'CMP-2026-A4F3', requester: 'Dr. Tahmina Karim (Dean, DIU)', reason: 'Police investigation request under Information & Communication Technology Act §57. Formal letter PROV-DIU/2026/118 attached.', basis: 'Penal Code §509 + ICT Act §57', requested: '2026-05-24 13:50', status: 'Awaiting 2nd approval' },
    { id: 'DAR-2026-0011', case: 'ALR-2026-7A88', requester: 'Senior Proctor (DIU)', reason: 'Vehicle theft report referred to Ashulia Thana, OC requested geofence trail.', basis: 'Penal Code §379', requested: '2026-05-23 09:30', status: 'Pending review' },
    { id: 'DAR-2026-0010', case: 'CMP-2026-A4F6', requester: 'Prof. Anwar Hossain (BUET pilot)', reason: 'Internal disciplinary committee — formal hearing notice issued.', basis: 'University statute 14(c)', requested: '2026-05-22 16:20', status: 'Pending review' },
  ];

  const services = [
    { name: 'AI Engine (Qwen3-8B)', status: 'healthy', latency: '412ms p50', err: '0.04%' },
    { name: 'Complaint Service', status: 'healthy', latency: '88ms p50', err: '0.00%' },
    { name: 'Alert Service', status: 'healthy', latency: '120ms p50', err: '0.02%' },
    { name: 'Notification Service', status: 'degraded', latency: '910ms p50', err: '1.20%' },
    { name: 'Evidence Storage', status: 'healthy', latency: '64ms p50', err: '0.00%' },
    { name: 'DMS Service', status: 'healthy', latency: '—', err: '0.00%' },
    { name: 'Multi-Tenant Service', status: 'healthy', latency: '52ms p50', err: '0.00%' },
    { name: 'Auth Service', status: 'healthy', latency: '78ms p50', err: '0.01%' },
  ];

  // 30 days of complaint inflow
  const inflow = Array.from({length: 30}, (_, i) => {
    const day = i + 1;
    const v = Math.round(8 + 6*Math.sin(i/3) + (i%5===0?6:0) + (i>22?4:0) + Math.random()*3);
    return { day: `${day}`, complaints: Math.max(2, v) };
  });

  const categoryBreakdown = [
    { name: 'Classroom', value: 38 },
    { name: 'Teacher Conduct', value: 21 },
    { name: 'Department', value: 14 },
    { name: 'Hostel', value: 19 },
    { name: 'Academic', value: 32 },
  ];

  const deptPerf = [
    { dept: 'SWE', Communication: 4.1, 'Resource Mgmt': 3.6, Responsiveness: 4.4, Fairness: 3.9, Events: 4.2 },
    { dept: 'CSE', Communication: 4.3, 'Resource Mgmt': 4.0, Responsiveness: 3.7, Fairness: 4.1, Events: 3.5 },
    { dept: 'EEE', Communication: 3.5, 'Resource Mgmt': 3.4, Responsiveness: 3.6, Fairness: 4.0, Events: 4.1 },
    { dept: 'BBA', Communication: 4.0, 'Resource Mgmt': 4.2, Responsiveness: 4.1, Fairness: 3.6, Events: 4.5 },
    { dept: 'English', Communication: 3.8, 'Resource Mgmt': 3.9, Responsiveness: 4.2, Fairness: 4.3, Events: 3.8 },
    { dept: 'Law', Communication: 4.4, 'Resource Mgmt': 3.5, Responsiveness: 3.4, Fairness: 4.5, Events: 3.6 },
  ];

  const classroomReports = [
    { room: 'KT-504', building: 'Knowledge Tower', count: 12, issues: ['AC broken','Lighting issue'], last: '2026-05-21', status: 'Under Review' },
    { room: 'KT-308', building: 'Knowledge Tower', count: 8, issues: ['Projector dead','HDMI faulty'], last: '2026-05-18', status: 'Resolved' },
    { room: 'AB1-201', building: 'Academic Bldg 1', count: 7, issues: ['Loose chairs','AC weak'], last: '2026-05-23', status: 'Under Review' },
    { room: 'KT-712', building: 'Knowledge Tower', count: 6, issues: ['Noise from corridor'], last: '2026-05-20', status: 'Submitted' },
    { room: 'AB2-105', building: 'Academic Bldg 2', count: 5, issues: ['Whiteboard worn','AC noisy'], last: '2026-05-19', status: 'Under Review' },
    { room: 'AB1-309', building: 'Academic Bldg 1', count: 4, issues: ['Door lock'], last: '2026-05-16', status: 'Resolved' },
    { room: 'KT-401', building: 'Knowledge Tower', count: 4, issues: ['Tube light flickering'], last: '2026-05-14', status: 'Submitted' },
  ];

  // Routine builder sample timetable (Sun-Thu, 8 slots)
  const days = ['Sun','Mon','Tue','Wed','Thu'];
  const slots = ['08:00','09:30','11:00','12:30','14:00','15:30','17:00','18:30'];
  // section color map
  const sectionColors = {
    '54-A': '#4A6B5C',
    '54-B': '#B8893A',
    '53-A': '#13294B',
    '53-B': '#C44536',
    '55-A': '#3A4754',
  };
  // build sample entries
  const timetable = [
    { d:0, s:0, code:'SWE-301', sec:'54-A', room:'KT-504', teacher:'Mahbub A.' },
    { d:0, s:1, code:'SWE-405', sec:'54-A', room:'KT-308', teacher:'Tahmina K.' },
    { d:0, s:3, code:'SWE-201', sec:'55-A', room:'AB1-201', teacher:'Farzana R.' },
    { d:1, s:0, code:'SWE-405', sec:'54-B', room:'KT-712', teacher:'Tahmina K.' },
    { d:1, s:2, code:'SWE-301', sec:'53-A', room:'KT-504', teacher:'Mahbub A.' },
    { d:1, s:4, code:'SWE-410', sec:'53-B', room:'AB2-105', teacher:'Imran C.' },
    { d:2, s:1, code:'SWE-201', sec:'55-A', room:'KT-401', teacher:'Farzana R.' },
    { d:2, s:3, code:'SWE-405', sec:'54-A', room:'KT-308', teacher:'Tahmina K.', conflict: true },
    { d:2, s:5, code:'SWE-410', sec:'53-A', room:'AB2-105', teacher:'Imran C.' },
    { d:3, s:0, code:'SWE-301', sec:'54-B', room:'KT-504', teacher:'Mahbub A.' },
    { d:3, s:2, code:'SWE-410', sec:'53-B', room:'AB2-105', teacher:'Imran C.' },
    { d:3, s:4, code:'SWE-201', sec:'55-A', room:'AB1-201', teacher:'Farzana R.' },
    { d:4, s:1, code:'SWE-405', sec:'54-B', room:'KT-712', teacher:'Tahmina K.' },
    { d:4, s:3, code:'SWE-301', sec:'53-A', room:'KT-504', teacher:'Mahbub A.' },
  ];

  const courses = [
    { code:'SWE-201', name:'Object Oriented Programming', credits:3, type:'Theory', sections:2, teacher:'Dr. Farzana Rahman' },
    { code:'SWE-301', name:'Algorithms', credits:3, type:'Theory', sections:3, teacher:'Dr. Mahbub Alam' },
    { code:'SWE-405', name:'Software Architecture Lab', credits:1, type:'Lab', sections:3, teacher:'Dr. Tahmina Karim' },
    { code:'SWE-410', name:'Distributed Systems', credits:3, type:'Theory', sections:2, teacher:'Dr. Imran Chowdhury' },
  ];

  // Anonymous culture reports
  const cultureReports = [
    { id:'GRV-2026-CR12', dept:'SWE', summary:'Lab access seems to depend on personal rapport with the instructor rather than schedule.', filed:'2026-05-22', pattern:true },
    { id:'GRV-2026-CR11', dept:'SWE', summary:'Lecturer A frequently arrives 15 minutes late; class is cut short.', filed:'2026-05-19', pattern:false },
    { id:'GRV-2026-CR10', dept:'EEE', summary:'Project group assignments appear biased toward students who attend instructor\u2019s personal coaching.', filed:'2026-05-16', pattern:true },
  ];

  return {
    complaints, alerts, tenants, audit, deanonRequests, services,
    inflow, categoryBreakdown, deptPerf, classroomReports,
    days, slots, timetable, sectionColors, courses, cultureReports,
  };
})();
