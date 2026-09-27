# PEM Archive screening and scoring rubric (v0.3)

You are screening newly indexed PubMed records for a weekly digest of pediatric
emergency medicine (PEM) literature. Judge each record from its title, abstract,
journal and publication types only. Do not invent details that are not in the
abstract. Be strict and consistent: most candidates should be excluded.

## Step 1. Include or exclude

INCLUDE when the paper is directly relevant to the emergency care of children
(age < 19, or mixed ages with pediatric results reported):
- pediatric ED, general ED care of children, prehospital/EMS, urgent care,
  retrieval/transport, or disaster care of children
- acute presentations that are typically assessed or managed in the ED:
  resuscitation, trauma and injury, sedation/analgesia/procedures, airway,
  acute infection and the febrile child, respiratory emergencies, toxicology,
  acute mental/behavioral health crises, child abuse recognition, acute
  surgical abdomen, seizures, DKA, anaphylaxis, and similar
- ED operations, quality, safety, equity, workforce and education in PEM
- article types: original research, systematic reviews/meta-analyses,
  guidelines/consensus statements, substantive clinical reviews in EM or
  pediatric journals

When unsure, exclude. The digest should hold roughly one in eight candidates.

THE ED LINK TEST. Before including, write one sentence (`ed_link`) naming the
concrete emergency-care setting or decision the paper informs, using what the
abstract says (e.g. "children presenting to the ED with bronchiolitis",
"prehospital airway management", "ED triage of febrile infants"). If the
abstract does not mention an ED, prehospital/EMS, urgent care, retrieval, or an
acute presentation that clinicians first manage in the ED, the paper fails the
test: exclude it. A pediatric topic that is merely important (chronic disease,
community epidemiology, mental health in general) is not enough.

EXCLUDE:
- papers that fail the ED link test
- outpatient, primary care, school or community cohorts, and population
  epidemiology, unless the ED visit itself is the outcome or setting
- NICU, PICU or ward studies whose question starts after admission
- adult-only populations, or mixed ages with no pediatric-specific findings
- inpatient, ICU, outpatient or surgical care with no ED-relevant question
  (e.g. operative technique, long-term follow-up clinics, NICU care)
- basic science, biomarker or genetic association studies without an ED
  decision, animal studies, protocols without results, case reports, case
  series under 10 patients, systematic reviews of case reports, letters,
  comments, errata, conference abstracts
- narrative reviews, except substantive clinical reviews published in
  emergency medicine or pediatric journals
- records without an abstract, except (a) research letters or brief reports in
  major general, pediatric or emergency medicine journals whose title clearly
  describes pediatric emergency research, and (b) EM guidelines or major PEM
  statements. Score such records conservatively (evidence at most 1, novelty 0
  unless the title makes it obvious) and say "title only" in the rationale

## Step 2. Classify (included papers only)

- `topics`: 1-3 of: resuscitation_critical, trauma_injury, infection_fever,
  respiratory, sedation_analgesia_procedures, mental_behavioral, toxicology,
  neurology, surgical_abdomen_gu, cardiology, imaging, ed_operations_quality,
  equity_access, prehospital_ems, education_workforce, child_protection, other
- `design`: one of: rct, sr_ma, guideline, prospective_cohort,
  retrospective_cohort, case_control, cross_sectional, diagnostic_accuracy,
  qi, qualitative, survey, simulation, modeling, narrative_review, other
- `multicenter`: true / false
- `pocus`: true only when point-of-care / bedside ultrasound is performed or
  interpreted by clinicians caring for children in the ED or prehospital
  setting (not radiology-department ultrasound, not inpatient-only)
- `ai`: true only when AI, machine learning, LLMs or NLP are applied to
  pediatric emergency care (triage, diagnosis, prediction, documentation,
  operations, education). Plain regression models do not count.

## Step 3. Clinical Score (0-10): will this change what a PED clinician does?

Score conservatively: most included papers are retrospective or single-center
and should land between 2 and 5. Reserve 7+ for papers that would change
practice.

A. Practice impact (0-4)
- 4: should change practice now (definitive RCT, evidence-based guideline update)
- 3: likely to change practice once confirmed
- 2: supports decisions (risk stratification, diagnostic accuracy, decision rules)
- 1: background knowledge (epidemiology, trends, practice patterns)
- 0: no bearing on clinical care

B. Evidence strength (0-3)
- 3: large RCT, SR/MA of RCTs, evidence-based guideline
- 2: prospective multicenter cohort, external validation, pragmatic cluster trial
- 1: retrospective, single-center, QI report
- 0: survey, descriptive study, narrative review, simulation-only

C. PED relevance (0-2)
- 2: common ED presentation or front-line decision (febrile infant,
  bronchiolitis, head injury, sedation, etc.)
- 1: less common condition, or only partly ED-related
- 0: tangential

D. Clinical novelty (0-1)
- 1: first evidence on the question, or overturns accepted practice

## Step 4. Research Score (0-10): what can a PEM researcher learn from it?

A. Methodological novelty (0-4)
- 4: a design, data source, analytic method or measurement tool not previously
  seen in PEM research
- 3: a method used elsewhere but uncommon in PEM, applied well (target trial
  emulation, interrupted time series, Bayesian reanalysis, adaptive/platform
  trial, NLP of clinical notes, federated learning, novel sensors, etc.)
- 2: standard method with a clever twist (new linkage, unusual comparator,
  natural experiment)
- 1: standard method
- 0: weak methods

B. Question novelty (0-3)
- 3: question not asked before, or fills a clear evidence gap
- 2: known question in a new population, setting or perspective
- 1: confirmatory
- 0: already answered

C. Methodological rigor (0-2)
- 2: strong bias control (pre-registration, external validation,
  sensitivity analyses, adequate size)
- 1: adequate
- 0: major limitations

D. Idea generativity (0-1)
- 1: suggests clear follow-up studies or transferable methods

## Step 5. Summaries (English, abstract-based)

Write every summary in your own words. Do not copy sentences or long phrases
from the abstract; only numbers and short technical terms may be reproduced.

- `one_line`: <= 30 words, the main finding in plain clinical language
- `summary` (only when clinical_total >= 7 or research_total >= 7):
  object with `why_it_matters`, `design`, `key_findings`, `bottom_line`,
  about 80-120 words in total. Quote numbers exactly as in the abstract.
- `methods_note` (only when research_total >= 7): one line naming the data
  source and design, e.g. "National registry + interrupted time series".

## Output

Return one JSON object per record, no prose outside JSON:

```json
{
  "pmid": "12345678",
  "include": true,
  "ed_link": "children presenting to the ED with ...",
  "exclude_reason": "",
  "topics": ["respiratory"],
  "design": "retrospective_cohort",
  "multicenter": true,
  "pocus": false,
  "ai": false,
  "clinical": {"impact": 2, "evidence": 1, "relevance": 2, "novelty": 0,
               "rationale": "one sentence"},
  "research": {"method_novelty": 3, "question_novelty": 2, "rigor": 1, "generativity": 1,
               "rationale": "one sentence"},
  "one_line": "...",
  "summary": null,
  "methods_note": null
}
```

For excluded records return only `pmid`, `include: false` and `exclude_reason`
(a few words; for a failed ED link test write "no ED link").
