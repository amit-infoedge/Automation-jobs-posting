"""
Database Connection and Operations Module
"""

import pyodbc
import pandas as pd
import threading
from typing import List, Optional, Dict, Any
import logging
from config import DB_DRIVER, DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD
from config import JOBS_TABLE, LOG_TABLE, JUNK_TABLE, JUNK_PROCESS

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Handles all database operations"""

    def __init__(self):
        self.connection = None
        self.cursor = None
        # One connection and cursor are shared by the whole run, including the
        # posting thread pool. pyodbc does not serialise concurrent use of a
        # single cursor, and doing so deadlocked a 66-job run, so every
        # statement below is executed under this lock.
        self._lock = threading.RLock()

    def connect(self) -> bool:
        """Establish database connection"""
        try:
            connection_string = (
                f"DRIVER={{{DB_DRIVER}}};"
                f"SERVER={DB_SERVER};"
                f"DATABASE={DB_NAME};"
                f"UID={DB_USER};"
                f"PWD={DB_PASSWORD}"
            )
            self.connection = pyodbc.connect(connection_string)
            self.cursor = self.connection.cursor()
            logger.info("Database connection established successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            return False

    def disconnect(self):
        """Close database connection"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {str(e)}")

    def fetch_jobs_for_posting(self, company_ids: List[int], limit: int = None) -> pd.DataFrame:
        """
        Fetch jobs from database for specific company IDs

        Args:
            company_ids: List of company IDs to fetch jobs for
            limit: Optional LIMIT for testing (e.g., 1 for single job test)

        Returns:
            DataFrame containing jobs to be posted
        """
        try:
            company_ids_str = ",".join(str(cid) for cid in company_ids)
            limit_clause = f"TOP {limit}" if limit else ""

            query = f"""
                SELECT {limit_clause} [Sr No] AS [Job Sent ID],[Process],[Assign To Executive] ,[Company id],
                case when [Company id]=123506651 then 'ABHISHEK.TIWARY@DB.COM' else [UserName] end as [UserName],
                [Priority],[Posting Type],[Company Name],[Source],[Position],[Location],[Exp],[URL],
                case when [Company id]=123506651 then '---' else [Responses] end as [Responses],
                [Executive Comments] as [Spl Instructions],[Team Comments],[Req ID],[CTC],[Industry],[PAF],
                [Job Id],[Job_Listing Comments],[Date],[Category],[Unique Sr No] AS [Lot No],[Executive Name],
                [Executive Status],[E_Status Added_Date] as [Jobs Sent Date],[E_Status Added_By] as [Jobs Sent By],
                [Job_Listing Status],[Job_Listing Updation_Date],[Assigned Date],[Blanket] ,[Assign By],
                [Recruiter Email],[Recruiter Link],[Top Account] ,[Company_Profile] as [Comp Prof],
                [Candidate Profile] as [Candidate Profile], [Functional Area] as [Functional Area],
                [Role] as [Role],[Job Description] as [JD], [KeyWords] as [Keyword],[Education] as [Education],
                [UG] as [UG],[PG] as [PG],[PPG] as [PPG],[Crawler ID] as [Crawler ID],[Template] as [Template],
                [Microsite] as [Microsite],[Logo] ,[Replied Date],[SubScription End Date],[Mandaory Keywords],
                case when len([Position])>=2 then [Position] else [Shared_Position] End as [Shared_Position],
                case when len([Location])>=2 then [Location] else [Shared_Location] End as [Shared_Location],
                [Approved Source],[Original Company ID],[Job Type],[Hiring For]
                FROM {JOBS_TABLE}
                WHERE [Company id] in ({company_ids_str})
                And [Executive Status] = 'Sent'
                and [Source] in ('Career Site')
                And ([Job_Listing Status] is null or [Job_Listing Status] = '')
            """
            logger.info(f"Fetching jobs for companies: {company_ids}{f' with LIMIT {limit}' if limit else ''}")
            logger.debug(f"Query: {query}")
            with self._lock:
                df = pd.read_sql(query, self.connection)
                
            df = df[df["JD"].fillna("").str.len() >= 300].copy()
            logger.info(f"Fetched {len(df)} jobs for posting")
            return df
        except Exception as e:
            logger.error(f"Error fetching jobs: {str(e)}")
            return pd.DataFrame()

    def update_job_status(self, job_id: str, status: str, comments: str = "") -> bool:
        """
        Update job listing status in database

        Args:
            job_id: Job ID to update
            status: New status value
            comments: Optional comments

        Returns:
            True if update successful, False otherwise
        """
        try:
            query = f"""
                UPDATE {JOBS_TABLE}
                SET [Job_Listing Status] = ?,
                    [Job_Listing Comments] = ?,
                    [Job_Listing Updation_Date] = GETDATE()
                WHERE [Job Id] = ?
            """
            with self._lock:
                self.cursor.execute(query, (status, comments, job_id))
                self.connection.commit()
            logger.info(f"Updated job {job_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
            with self._lock:
                self.connection.rollback()
            return False

    def fetch_junk_words(self) -> Dict[str, List[str]]:
        """
        Load the per-company junk phrases stripped from JDs.

        Mirrors RibbonController.cs:115, which loads
        `select * from crawler.junk where process='offline'` once at startup.

        Returns:
            {company_id: [phrase, ...]}, empty on failure so posting continues
        """
        try:
            query = f"SELECT [Company Id], [Junk] FROM {JUNK_TABLE} WHERE [process] = ?"
            with self._lock:
                df = pd.read_sql(query, self.connection, params=(JUNK_PROCESS,))
        except Exception as e:
            logger.error(f"Could not load junk words: {str(e)}")
            return {}

        junk_map: Dict[str, List[str]] = {}
        for _, row in df.iterrows():
            company_id = row.get('Company Id')
            phrase = row.get('Junk')

            if company_id is None or phrase is None:
                continue
            phrase = str(phrase)
            if not phrase.strip():
                continue

            # Company Id comes back as a float (it is numeric in SQL), so
            # 27117.0 has to become "27117" to match the ids we key on.
            try:
                key = str(int(float(company_id)))
            except (TypeError, ValueError):
                key = str(company_id).strip()

            junk_map.setdefault(key, []).append(phrase)

        total = sum(len(v) for v in junk_map.values())
        logger.info(f"Loaded {total} junk phrases for {len(junk_map)} companies")
        return junk_map

    def update_listing_status_by_sr_no(self, sr_no: Any, status: str, comments: str) -> bool:
        """
        Set the listing status/comments for a row identified by [Sr No].

        Needed for jobs that are rejected before posting - they have no [Job Id]
        yet, so update_job_status cannot find them.

        Args:
            sr_no: [Sr No] of the row (aliased [Job Sent ID] in the fetch query)
            status: Value for [Job_Listing Status]
            comments: Value for [Job_Listing Comments]

        Returns:
            True if a row was updated
        """
        if sr_no in (None, ""):
            logger.error("Cannot update listing status: no [Sr No] provided")
            return False

        try:
            query = f"""
                UPDATE {JOBS_TABLE}
                SET [Job_Listing Status] = ?,
                    [Job_Listing Comments] = ?,
                    [Job_Listing Updation_Date] = GETDATE()
                WHERE [Sr No] = ?
            """
            with self._lock:
                self.cursor.execute(query, (status, comments, sr_no))
                affected = self.cursor.rowcount
                self.connection.commit()

            if affected < 1:
                logger.warning(f"No row matched [Sr No]={sr_no}; nothing updated")
                return False

            logger.info(f"[Sr No]={sr_no} marked '{status}': {comments}")
            return True
        except Exception as e:
            logger.error(f"Error updating listing status for [Sr No]={sr_no}: {str(e)}")
            try:
                with self._lock:
                    self.connection.rollback()
            except Exception:
                pass
            return False

    def mark_job_posted(self, sr_no: Any, job_id: Any, title: str, location: str,
                        all_info: str) -> bool:
        """
        Write back a successful post to the source row, identified by [Sr No].

        [Position]/[Location] are rewritten because the posted title and location
        are the cleaned values, which can differ from what the row came in with.

        Args:
            sr_no: [Sr No] of the row (aliased [Job Sent ID] in the fetch query)
            job_id: Job ID returned by the publish API
            title: Posted job title
            location: Posted job location
            all_info: Percent-separated snapshot of the posted values

        Returns:
            True if a row was updated
        """
        if sr_no in (None, ""):
            logger.error("Cannot mark job posted: no [Sr No] provided")
            return False

        try:
            query = f"""
                UPDATE {JOBS_TABLE}
                SET [Job_Listing Status] = 'Posted',
                    [Automated Posted] = 'Yes',
                    [Assign To Executive]='Tech_Automation',
                    [Position] = ?,
                    [Location] = ?,
                    [Job_Listing Updation_Date] = GETDATE(),
                    [Job Id] = ?,
                    [All_Info] = ?,
                    [Shared_Position] = ?,
                    [Shared_Location] = ?
                WHERE [Sr No] = ?
            """
            with self._lock:
                self.cursor.execute(
                    query,
                    (title, location, job_id, all_info, title, location, sr_no)
                )
                affected = self.cursor.rowcount
                self.connection.commit()

            if affected < 1:
                logger.warning(f"No row matched [Sr No]={sr_no}; nothing updated")
                return False

            logger.info(f"[Sr No]={sr_no} marked 'Posted' with [Job Id]={job_id}")
            return True
        except Exception as e:
            logger.error(f"Error marking [Sr No]={sr_no} posted: {str(e)}")
            try:
                with self._lock:
                    self.connection.rollback()
            except Exception:
                pass
            return False

    def insert_job_posting_result(self, result_data: Dict[str, Any]) -> bool:
        """
        Insert job posting result into database

        Args:
            result_data: Dictionary containing result information

        Returns:
            True if insert successful, False otherwise
        """
        try:
            # Prepare columns and values
            columns = ", ".join(f"[{col}]" for col in result_data.keys())
            placeholders = ", ".join("?" * len(result_data))
            values = tuple(result_data.values())

            query = f"INSERT INTO {JOBS_TABLE} ({columns}) VALUES ({placeholders})"
            with self._lock:
                self.cursor.execute(query, values)
                self.connection.commit()
            logger.info(f"Inserted job posting result into database")
            return True
        except Exception as e:
            logger.error(f"Error inserting job result: {str(e)}")
            with self._lock:
                self.connection.rollback()
            return False

    def log_posting_attempt(self, log_data: Dict[str, Any]) -> bool:
        """
        Log job posting attempt to RRR_log table

        Args:
            log_data: Dictionary containing log information

        Returns:
            True if log inserted successfully
        """
        try:
            columns = ", ".join(f"[{col}]" for col in log_data.keys())
            placeholders = ", ".join("?" * len(log_data))
            values = tuple(log_data.values())

            query = f"INSERT INTO {LOG_TABLE} ({columns}) VALUES ({placeholders})"
            with self._lock:
                self.cursor.execute(query, values)
                self.connection.commit()
            logger.info(f"Logged posting attempt for job {log_data.get('file', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Error logging posting attempt: {str(e)}")
            with self._lock:
                self.connection.rollback()
            return False

    def check_job_exists_in_log(self, job_id: str, days: int = 30) -> bool:
        """
        Check if job already exists in RRR_log within last N days

        Args:
            job_id: Job ID to check
            days: Number of days to look back

        Returns:
            True if job exists, False otherwise
        """
        try:
            query = f"""
                SELECT COUNT(*) as cnt FROM {LOG_TABLE}
                WHERE [file] = ? AND [Request_Date] >= DATEADD(day, -{days}, GETDATE())
            """
            with self._lock:
                self.cursor.execute(query, (job_id,))
                result = self.cursor.fetchone()
            exists = result[0] > 0 if result else False
            logger.info(f"Job {job_id} exists in log: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking job in log: {str(e)}")
            return False

    def execute_query(self, query: str, params: tuple = ()) -> bool:
        """
        Execute a custom query

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                self.cursor.execute(query, params)
                self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            with self._lock:
                self.connection.rollback()
            return False

    def fetch_query(self, query: str, params: tuple = ()) -> pd.DataFrame:
        """
        Execute a SELECT query and return results as DataFrame

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            DataFrame with query results
        """
        try:
            with self._lock:
                return pd.read_sql(query, self.connection, params=params)
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return pd.DataFrame()


class DatabaseManager:
    """Singleton pattern for database management"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.db = DatabaseConnection()
            cls._instance.db.connect()
        return cls._instance

    def __getattr__(self, name):
        return getattr(self.db, name)

    def __del__(self):
        if self.db:
            self.db.disconnect()
