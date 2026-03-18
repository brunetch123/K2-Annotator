# K2 GC-MS Pipeline Presentation Slides Guide

## Overview
This guide accompanies the 12 assertion-evidence style diagrams generated for your Computer & Electrical Engineering department seminar.

**Generated Files Location:** `presentation_figures/`

All diagrams are high-resolution (300 DPI) PNG files ready for insertion into PowerPoint, Keynote, or LaTeX Beamer presentations.

---

## Slide-by-Slide Breakdown

### **Slide 1: System Overview**
**File:** `slide1_system_overview.png` (200 KB)

**Assertion:** "K2 automates the complete workflow from raw instrument files to Level 2 compound identification with hazard assessment"

**Visual Elements:**
- Three entry points (left side): .D files, .mzML, MZmine output
- Five main pipeline stages: MSConvert → MZmine → Universal Parser → Matching Engine → Reporter
- Two outputs: CSV and PDF reports
- Key features highlighted at bottom (Level 2 ID, BFF, IS Normalization, RI Calibration)

**Presentation Tips:**
- Emphasize the modular architecture
- Note that all stages are automated
- Highlight the flexibility of multiple entry points

---

### **Slide 2: Modular Entry Points**
**File:** `slide2_entry_points.png` (173 KB)

**Assertion:** "Users can enter the pipeline at three stages depending on their data processing stage"

**Visual Elements:**
- Central decision diamond: "Data Format?"
- Three parallel paths showing different workflow lengths
- Path 1 (full pipeline): 4 stages
- Path 2 (skip conversion): 3 stages
- Path 3 (matching only): 2 stages

**Presentation Tips:**
- Explain how this reduces computational redundancy
- Note that this is useful for iterative analysis (re-run matching with different parameters without re-processing raw data)

---

### **Slide 3: Universal Parser Architecture**
**File:** `slide3_universal_parser.png` (195 KB)

**Assertion:** "A single parser automatically detects and handles both MS-DIAL and MZmine output formats"

**Visual Elements:**
- Top: UniversalParser class with `detect_format()` method
- Branching: MS-DIAL Parser (left) and MZmine Parser (right)
- Code snippet showing format detection logic
- Convergence: Both produce unified Feature objects

**Presentation Tips:**
- This is a classic **Strategy Pattern** from software design
- Emphasize the benefit: users don't need to specify their input format
- Highlight the unified Feature object as the abstraction layer

---

### **Slide 4: Feature Data Model**
**File:** `slide4_feature_model.png` (214 KB)

**Assertion:** "Each detected chromatographic feature is represented as an object containing spectral, quantitative, and metadata"

**Visual Elements:**
- UML-style class diagram
- Attributes organized by category: Identifiers, Spectral Data, Quantitative Data, Quality Metrics
- Methods section showing `calculate_bff()`
- Example instantiation code at bottom

**Presentation Tips:**
- This is the core data structure of the system
- Explain how object-oriented design encapsulates both data and behavior
- Note the extensibility: easy to add new attributes or methods

---

### **Slide 5: Blank Feature Filtering (BFF)**
**File:** `slide5_bff_filtering.png` (169 KB)

**Assertion:** "Background contamination is removed by comparing sample abundances to statistical thresholds calculated from blank samples"

**Visual Elements:**
- Mathematical formula at top: Threshold = 5 × (μ_blank + 3σ_blank)
- Box plot showing distributions: Blanks, Sample (Fail), Sample (Pass)
- Red dashed line showing threshold
- Decision logic box (right side)

**Presentation Tips:**
- This is a **statistical quality control** method
- The 5× multiplier and 3σ are conservative to minimize false negatives
- Explain how this removes laboratory artifacts and environmental contamination

---

### **Slide 6: Internal Standard Normalization**
**File:** `slide6_is_normalization.png` (226 KB)

**Assertion:** "Three automated methods correct for injection variability by normalizing to internal standard peak areas"

**Visual Elements:**
- Three parallel workflow branches showing different detection methods
- All converge to central "Calculate Normalization Factors" stage
- Formula at bottom showing calculation
- Color coding: each method has distinct color

**Presentation Tips:**
- Method 1 (Manual): For when IS areas are obtained externally
- Method 2 (Auto m/z+RI): Fast, requires known IS properties
- Method 3 (Auto MSP): Most robust, uses full spectral matching
- Emphasize that normalization happens **before** BFF filtering

---

### **Slide 7: Library Matching Engine**
**File:** `slide7_matching_funnel.png` (156 KB)

**Assertion:** "Candidate matches are filtered hierarchically by retention index window, spectral similarity, and high-resolution formula matching"

**Visual Elements:**
- Funnel diagram showing progressive filtering
- Stage 1: 5,432 features → RI window → 2,156 candidates
- Stage 2: Spectral similarity → 843 candidates
- Stage 3: RI error check → 412 candidates
- Stage 4: RHRMF formula → 287 final matches
- 95% reduction highlighted

**Presentation Tips:**
- This is a **performance optimization** strategy
- Binary search on RI reduces complexity from O(n²) to O(n log n)
- Each filter is computationally cheap, expensive operations only on small candidate sets

---

### **Slide 8: Spectral Similarity Scoring**
**File:** `slide8_spectral_scoring.png` (192 KB)

**Assertion:** "Spectral matches are quantified using dot product and reverse dot product to assess forward and reverse similarity"

**Visual Elements:**
- Mirror spectrum plot: Query (top, blue) vs Library (bottom, orange)
- Green dashed lines highlight matching peaks
- Mathematical formulas at bottom showing dot product calculation
- Threshold noted: > 0.70

**Presentation Tips:**
- This is the **standard method** in mass spectrometry informatics
- Dot product is essentially a normalized cosine similarity
- Reverse dot product accounts for additional peaks in query spectrum
- Threshold of 0.70 is based on literature for Level 2 identification

---

### **Slide 9: Retention Index Calibration**
**File:** `slide9_ri_calibration.png` (261 KB)

**Assertion:** "Retention time is converted to retention index using n-alkane standards for instrument-independent identification"

**Visual Elements:**
- Scatter plot: RT vs RI with n-alkane standards (green circles)
- Cubic polynomial regression curve (blue line)
- Example unknown compound (red star) with annotation showing interpolation
- Equation box at bottom

**Presentation Tips:**
- Retention Index (RI) is the **Kovats Index** used in GC-MS
- RI is instrument-independent (unlike RT which varies with flow rate, column condition)
- Cubic interpolation is more accurate than linear for wide RT ranges
- This is why the pipeline can match against libraries from different instruments

---

### **Slide 10: Level 2 Identification Logic**
**File:** `slide10_level2_logic.png` (184 KB)

**Assertion:** "Matches achieve Level 2 confidence when spectral score, retention index error, and formula match all pass thresholds"

**Visual Elements:**
- Three input gates: Spectral Score, RI Error, RHRMF Formula Match
- AND logic gate (orange)
- Decision diamond
- Two outcomes: Level 2 ID (green) or No Match (red)
- Reference to Koelmel et al. 2022 at bottom

**Presentation Tips:**
- This follows **metabolomics community standards** (Metabolomics Standards Initiative)
- Level 2 = "Probable structure by library spectrum match"
- All three criteria must pass (Boolean AND logic)
- RHRMF = "Relative High-Resolution Mass Filtering" for formula validation

---

### **Slide 11: Surrogate Standard Recovery**
**File:** `slide11_surrogate_recovery.png` (235 KB)

**Assertion:** "Isotope-labeled surrogate standards track extraction efficiency and matrix effects through the workflow"

**Visual Elements:**
- Workflow: Spike → Extract → Analysis
- Parallel paths: Reference samples vs Test samples
- Recovery calculation in center
- QC zones at bottom: Green (70-130%), Yellow (50-70%, 130-150%), Red (<50%, >150%)
- Formula showing recovery calculation

**Presentation Tips:**
- Surrogates are **quality control** compounds (13C or deuterated)
- Recovery outside 70-130% indicates method issues
- This is required for EPA methods and good lab practice
- Separate from internal standards (which correct variation)

---

### **Slide 12: Multi-Format Report Generation**
**File:** `slide12_report_generation.png` (242 KB)

**Assertion:** "Results are automatically compiled into CSV tables for data analysis and PDF reports with annotated spectra and hazard matrices"

**Visual Elements:**
- Split screen: CSV (left) vs PDF (right)
- CSV mockup showing data columns
- PDF mockup showing visual elements: mirror spectra, structures, hazard matrix
- EPA CompTox API integration shown at bottom

**Presentation Tips:**
- Dual output format serves different needs:
  - **CSV**: Machine-readable, for statistical analysis, database import
  - **PDF**: Human-readable, for manual review, publication figures
- EPA CompTox integration provides toxicity data (GHS classifications)
- Automated generation eliminates manual reporting errors

---

## Technical Conventions Used

### Software Engineering Diagrams:
- **UML Class Diagrams** (Slide 3, 4): Standard object-oriented design notation
- **Activity Diagrams** (Slide 1, 2): Workflow and process flow
- **Flowcharts** (Slide 2, 6, 11): Standard symbols (rectangle=process, diamond=decision)

### Data Visualizations:
- **Box Plots** (Slide 5): Statistical distributions
- **Mirror Plots** (Slide 8): Standard in mass spectrometry
- **Calibration Curves** (Slide 9): Regression plots
- **Funnel Diagrams** (Slide 7): Progressive filtering

### Logic Diagrams:
- **Logic Gates** (Slide 10): Boolean decision logic

### Color Coding:
- **Blue**: Data flow and general processes
- **Green**: Success outcomes, passing filters
- **Red**: Failures, rejections
- **Orange**: Decisions, warnings
- **Gray**: Supporting information

---

## Recommended Slide Order

The current order tells a logical story:

1. **Introduction** (Slides 1-2): Big picture, system overview
2. **Data Architecture** (Slides 3-4): How data is represented
3. **Preprocessing** (Slides 5-6): Quality control and normalization
4. **Core Algorithm** (Slides 7-10): Matching engine logic
5. **Quality Control** (Slide 11): Method validation
6. **Output** (Slide 12): Results and reporting

---

## Customization Tips

### If you want to modify the diagrams:

1. Open `generate_presentation_diagrams.py`
2. Each slide has its own function: `generate_slide1()` through `generate_slide12()`
3. Modify colors, text, layout as needed
4. Re-run: `python generate_presentation_diagrams.py`

### Common modifications:

**Change colors:**
```python
COLOR_PROCESS = '#4472C4'  # Blue for processes
COLOR_SUCCESS = '#70AD47'  # Green for success
```

**Adjust figure size:**
```python
fig, ax = plt.subplots(figsize=(12, 8))  # Width, Height in inches
```

**Change DPI (resolution):**
```python
plt.savefig(..., dpi=300)  # 300 for print, 150 for screen
```

---

## Presentation Structure Suggestion

### Total: ~30-40 minutes

1. **Introduction (5 min)**
   - Problem statement: Non-targeted screening challenges
   - K2 solution overview (Slide 1)

2. **Architecture (10 min)**
   - Modular design (Slide 2)
   - Universal parser (Slide 3)
   - Data model (Slide 4)

3. **Processing Pipeline (10 min)**
   - BFF filtering (Slide 5)
   - IS normalization (Slide 6)
   - RI calibration (Slide 9)

4. **Matching Algorithm (8 min)**
   - Hierarchical filtering (Slide 7)
   - Spectral scoring (Slide 8)
   - Level 2 criteria (Slide 10)

5. **Quality Assurance (4 min)**
   - Surrogate recovery (Slide 11)

6. **Output & Applications (3 min)**
   - Report generation (Slide 12)
   - Real-world results example

7. **Q&A (10 min)**

---

## File Specifications

- **Format:** PNG (lossless)
- **Resolution:** 300 DPI (publication quality)
- **Color Space:** RGB
- **Size Range:** 156-261 KB per file
- **Total Package:** ~2.5 MB

All files are optimized for:
- PowerPoint/Keynote insertion
- LaTeX Beamer presentations
- Print reproduction
- Online viewing

---

## Additional Resources

### For the presentation:
- Include K2 logo (if available): `K2Icon.png` or `K2Logo2.png`
- Reference documentation: `K2_USER_GUIDE.md`
- Implementation details: `K2_IMPLEMENTATION_SUMMARY.md`

### For questions about specific algorithms:
- BFF: See `scripts/src/universal_parser.py` → `Feature.calculate_bff()`
- Spectral scoring: See `scripts/src/spectral_math.py`
- Library matching: See `scripts/src/matching_engine.py`

---

## Citation

If presenting published work, cite:
- Koelmel et al. (2022) for Level 2 identification criteria
- Your own publication (if applicable)

---

**Generated:** February 9, 2026
**Version:** K2 v3.0.2
**Author:** Claude (Anthropic) + K2 Development Team
