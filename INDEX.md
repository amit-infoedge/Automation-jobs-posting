# Job Posting Automation Framework - File Index

## 📚 Complete File Listing

### **Core Application Files** (2,100+ lines of code)

#### 1. **config.py** (90 lines)
- Database connection settings
- API configuration and timeouts  
- Target company IDs [27117, 16987]
- Email and output settings
- **Start here to**: Configure your environment

#### 2. **models.py** (280+ lines)
- 10+ data model classes using @dataclass
- Complete Job model with validation()
- Request/Response models
- Sub-user and company information
- **Start here to**: Understand data structures

#### 3. **database.py** (260 lines)
- DatabaseConnection class for SQL operations
- DatabaseManager singleton
- fetch_jobs_for_posting() method
- Update status and log attempts
- **Start here to**: Access database

#### 4. **job_processor.py** (450+ lines)
- JobValidator: Validate titles, keywords, locations
- JobProcessor: Parse exp/salary, fill blanks, predict fields
- JobBuilder: Build complete Job from raw data
- **Start here to**: Process and transform job data

#### 5. **api_client.py** (350+ lines)
- NaukriAPIClient with retry logic
- @retry_on_exception decorator
- get_operations(), save_job_draft(), publish_job()
- get_company_details(), get_sub_users()
- **Start here to**: Make API calls

#### 6. **job_poster.py** (400+ lines)
- JobPoster orchestrator
- initialize() company and users
- post_job() single job
- post_jobs_bulk() concurrent posting
- **Start here to**: Post jobs

#### 7. **utils.py** (300+ lines)
- DataCleaner: Clean strings, numbers, DataFrames
- ResponseParser: Parse responses, extract job IDs
- FileManager: Save/load CSV, JSON
- TimeUtils: Timestamps
- ValidationUtils: Email, URL validation
- **Start here to**: Use utility functions

#### 8. **main.py** (350+ lines)
- JobPostingAutomation class
- run() main automation workflow
- fetch_jobs_from_db()
- process_company_jobs()
- save_results()
- **Start here to**: Run the complete automation

#### 9. **examples.py** (450+ lines)
- 10 working examples
- Demonstrates all major features
- Can be run standalone
- **Start here to**: Learn by example
```bash
python examples.py
```

---

### **Documentation Files** (1,200+ lines)

#### 📖 **README.md** (600+ lines)
**Complete reference guide**
- Overview and architecture
- Component descriptions
- Complete workflow diagram
- Usage examples
- Data models reference
- Database schema
- Error handling
- Configuration guide
- Troubleshooting
- **Read for**: Complete understanding

#### 📐 **STRUCTURE.md** (400+ lines)
**Architecture and design overview**
- Detailed file descriptions
- Data flow diagrams
- Class relationships
- Configuration hierarchy
- Error handling strategy
- Testing strategy
- Performance metrics
- **Read for**: Understanding design

#### ⚡ **QUICKSTART.md** (200+ lines)
**Get up and running in 5 minutes**
- Step-by-step setup
- Common tasks
- Troubleshooting
- Monitoring tips
- Support contacts
- **Read for**: Quick start

#### 📊 **PROJECT_SUMMARY.md** (300+ lines)
**Executive summary and metrics**
- Key features list
- Architecture overview
- Workflow description
- Performance metrics
- Quality checklist
- **Read for**: High-level overview

#### 📋 **INDEX.md** (This file)
**File index and navigation guide**
- What's in each file
- Reading recommendations
- Quick reference
- **Read for**: Orientation

---

### **Configuration Files** (1 file)

#### ⚙️ **requirements.txt** (20 lines)
**Python package dependencies**
```
pandas >= 1.3.0
numpy >= 1.21.0
pyodbc >= 4.0.0
requests >= 2.26.0
openpyxl >= 3.6.0
python-dateutil >= 2.8.2
```

**Install with**:
```bash
pip install -r requirements.txt
```

---

## 🎯 Quick Navigation

### "I want to..."

#### **Get started quickly**
1. Read: [QUICKSTART.md](QUICKSTART.md)
2. Install: `pip install -r requirements.txt`
3. Run: `python examples.py`
4. Configure: Edit `main.py` with cookies
5. Execute: `python main.py`

#### **Understand the code**
1. Read: [STRUCTURE.md](STRUCTURE.md) - Architecture
2. Read: [models.py](models.py) - Data models
3. Read: [job_processor.py](job_processor.py) - Business logic
4. Trace: [main.py](main.py) - Workflow flow

#### **Learn by example**
1. Run: `python examples.py`
2. Read: [examples.py](examples.py) - 10 examples
3. Modify examples to test

#### **Deploy to production**
1. Read: [README.md](README.md) - Full reference
2. Configure: [config.py](config.py)
3. Setup: Database and directories
4. Test: `python examples.py`
5. Schedule: Windows Task Scheduler

#### **Debug an issue**
1. Check: `C:\logs\job_posting.log`
2. Read: [README.md](README.md#troubleshooting) - Troubleshooting
3. Review: Error CSV file
4. Check: [database.py](database.py) - DB queries

#### **Extend functionality**
1. Understand: Architecture in [STRUCTURE.md](STRUCTURE.md)
2. Study: [job_processor.py](job_processor.py) - Business logic
3. Reference: [models.py](models.py) - Data models
4. Implement: Your feature
5. Test: Add example in [examples.py](examples.py)

---

## 📑 File Statistics

```
CORE MODULES (7 files)
├─ config.py           90 lines   ▓░░░░░░░░░  5%
├─ models.py          280 lines   ▓▓░░░░░░░░  13%
├─ database.py        260 lines   ▓▓░░░░░░░░  12%
├─ job_processor.py   450 lines   ▓▓▓▓░░░░░░  21%
├─ api_client.py      350 lines   ▓▓▓░░░░░░░  17%
├─ job_poster.py      400 lines   ▓▓▓░░░░░░░  19%
└─ utils.py           300 lines   ▓▓░░░░░░░░  14%
                    ─────────────
TOTAL              2,130 lines   100%

APPLICATION (2 files)
├─ main.py           350 lines   ▓▓▓░░░░░░░  44%
└─ examples.py       450 lines   ▓▓▓▓░░░░░░  56%
                    ─────────────
TOTAL              800 lines

DOCUMENTATION (4 files)
├─ README.md         600+ lines
├─ STRUCTURE.md      400+ lines
├─ QUICKSTART.md     200+ lines
└─ PROJECT_SUMMARY.md 300+ lines
                    ─────────────
TOTAL             1,500+ lines

CONFIGURATION (1 file)
└─ requirements.txt   20 lines

═════════════════════════════════════════════
GRAND TOTAL         ~4,450 lines
```

---

## 🔗 Module Dependencies

```
main.py
├─ config.py          (configuration)
├─ database.py        (fetch jobs)
├─ job_processor.py   (process jobs)
├─ job_poster.py      (post jobs)
│  ├─ api_client.py
│  ├─ job_processor.py
│  ├─ models.py
│  └─ job_poster.py
└─ utils.py           (utilities)
    ├─ models.py
    └─ config.py

examples.py
├─ models.py
├─ job_processor.py
├─ database.py
├─ api_client.py
├─ job_poster.py
└─ utils.py
```

---

## 📚 Learning Recommendations

### For **Beginners**
1. **Day 1**: [QUICKSTART.md](QUICKSTART.md) - Get familiar
2. **Day 2**: [examples.py](examples.py) - See it work
3. **Day 3**: [models.py](models.py) - Learn data structures
4. **Day 4**: [job_processor.py](job_processor.py) - Understand logic

### For **Developers**
1. **Start**: [STRUCTURE.md](STRUCTURE.md) - Architecture
2. **Study**: [main.py](main.py) - Workflow
3. **Review**: All modules - Implementation
4. **Extend**: [examples.py](examples.py) - Add tests

### For **DevOps/Admin**
1. **Deploy**: [QUICKSTART.md](QUICKSTART.md) - Setup
2. **Configure**: [config.py](config.py) - Settings
3. **Monitor**: [README.md](README.md#monitoring) - Logs
4. **Troubleshoot**: [README.md](README.md#troubleshooting) - Issues

---

## 🔍 Finding Things

### By Topic

| Topic | File | Line # |
|-------|------|--------|
| Database queries | database.py | ~50-150 |
| Job validation | job_processor.py | ~50-150 |
| API calls | api_client.py | ~80-250 |
| Job posting | job_poster.py | ~150-300 |
| Data models | models.py | All |
| Workflow | main.py | ~150-250 |
| Examples | examples.py | All |
| Configuration | config.py | All |
| Utilities | utils.py | All |

### By Function

| Function | File |
|----------|------|
| Fetch jobs | database.py::fetch_jobs_for_posting() |
| Parse experience | job_processor.py::parse_experience() |
| Validate job | models.py::Job.validate() |
| Post job | job_poster.py::post_job() |
| Retry API | api_client.py::@retry_on_exception |
| Build payload | job_poster.py::prepare_job_payload() |
| Main flow | main.py::run() |

---

## 🚀 Execution Flow

```
START
  ↓
main.py::main()
  ├─ JobPostingAutomation.__init__()
  ├─ automation.run()
  │  ├─ fetch_jobs_from_db()
  │  │  └─ database.py::fetch_jobs_for_posting()
  │  ├─ For each company:
  │  │  ├─ process_company_jobs()
  │  │  │  ├─ JobPoster.initialize()
  │  │  │  │  └─ api_client.py::get_company_details()
  │  │  │  ├─ JobBuilder.build_from_request()
  │  │  │  │  └─ job_processor.py::parse_*()
  │  │  │  └─ JobPoster.post_jobs_bulk()
  │  │  │     ├─ job_poster.py::post_job()
  │  │  │     │  ├─ api_client.py::save_job_draft()
  │  │  │     │  └─ api_client.py::publish_job()
  │  │  │     └─ Parallel execution (5 workers)
  │  ├─ save_results()
  │  │  └─ utils.py::FileManager.save_csv()
  │  └─ generate_summary()
  ├─ Print results
  └─ Exit
```

---

## 📝 Code Examples Location

| Example | File | Lines |
|---------|------|-------|
| Validate job | examples.py | 15-40 |
| Parse data | examples.py | 55-75 |
| Validate keywords | examples.py | 85-110 |
| Fetch from DB | examples.py | 120-145 |
| Build job | examples.py | 155-185 |
| Apply rules | examples.py | 195-220 |
| Post single | examples.py | 230-280 |
| Clean data | examples.py | 290-315 |
| Validate fields | examples.py | 325-360 |
| Time utilities | examples.py | 370-400 |

---

## ✅ Checklist for First-Time Users

- [ ] Read QUICKSTART.md
- [ ] Install requirements: `pip install -r requirements.txt`
- [ ] Run examples: `python examples.py`
- [ ] Review models.py for data structures
- [ ] Read job_processor.py for business logic
- [ ] Study main.py for workflow
- [ ] Configure authentication in main.py
- [ ] Test with sample data
- [ ] Check logs in C:\logs\job_posting.log
- [ ] Review CSV output

---

## 🆘 Need Help?

1. **Quick answers**: Check [QUICKSTART.md](QUICKSTART.md)
2. **Complete reference**: Read [README.md](README.md)
3. **Architecture help**: Study [STRUCTURE.md](STRUCTURE.md)
4. **Code examples**: Run [examples.py](examples.py)
5. **Troubleshooting**: See [README.md#troubleshooting](README.md)
6. **Specific code**: Search in respective module file

---

## 📞 Support

**For questions**: See [QUICKSTART.md#support](QUICKSTART.md)  
**For issues**: Check logs in C:\logs\job_posting.log  
**For errors**: Review error CSV in C:\a\

---

## 🎓 Recommended Reading Order

### **Option A: Quick Start** (2 hours)
1. QUICKSTART.md
2. examples.py (run and read)
3. Start using!

### **Option B: Complete Understanding** (1 day)
1. QUICKSTART.md
2. STRUCTURE.md
3. models.py
4. job_processor.py
5. api_client.py
6. job_poster.py
7. main.py
8. README.md

### **Option C: Developer Deep Dive** (2 days)
1. All of Option B
2. database.py (in detail)
3. utils.py (in detail)
4. examples.py (run all, modify)
5. README.md - Troubleshooting section

---

## 📊 File Purposes at a Glance

| File | Purpose | Complexity |
|------|---------|-----------|
| config.py | Settings | ⭐ Easy |
| models.py | Data structures | ⭐ Easy |
| database.py | DB access | ⭐⭐ Medium |
| job_processor.py | Business logic | ⭐⭐⭐ Hard |
| api_client.py | API integration | ⭐⭐⭐ Hard |
| job_poster.py | Orchestration | ⭐⭐⭐ Hard |
| utils.py | Helpers | ⭐ Easy |
| main.py | Workflow | ⭐⭐ Medium |
| examples.py | Examples | ⭐ Easy |

---

**Last Updated**: August 31, 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✓
