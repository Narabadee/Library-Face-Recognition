from datetime import datetime, date
from database.models import db, Student, AttendanceLog

class AttendanceService:
    """Service for handling student attendance logic"""
    
    @staticmethod
    def get_student_status(student_id_str):
        """
        Check current status of a student (inside/outside).
        Returns: (status: str, student: Student, last_log: AttendanceLog)
        """
        student = Student.query.filter_by(student_id=student_id_str).first()
        if not student:
            return None, None, None
            
        # Find latest log for this student
        # Order by check_in time descending
        last_log = AttendanceLog.query.filter_by(student_id=student.id)\
                    .order_by(AttendanceLog.check_in.desc()).first()
        
        status = 'outside'
        if last_log and last_log.check_out is None and last_log.date == date.today():
             # If check_out is None AND it's today's log -> Inside
             # (Actually, even if it's yesterday's log and they forgot to checkout, 
             # logic might vary, but usually 'inside' implies active session)
             status = 'inside'
        
        return status, student, last_log

    @staticmethod
    def check_in(student_id_str):
        """
        Record check-in for a student
        Returns: (success, message, log_obj)
        """
        status, student, last_log = AttendanceService.get_student_status(student_id_str)
        
        if not student:
            return False, "Student not found", None
            
        if status == 'inside':
            return False, "Already checked in", None
            
        # Create new log
        new_log = AttendanceLog(
            student_id=student.id,
            check_in=datetime.now(),
            date=date.today()
        )
        db.session.add(new_log)
        try:
            db.session.commit()
            return True, "Check-in successful", new_log
        except Exception as e:
            db.session.rollback()
            return False, f"Database error: {str(e)}", None

    @staticmethod
    def check_out(student_id_str):
        """
        Record check-out for a student
        Returns: (success, message, log_obj)
        """
        status, student, last_log = AttendanceService.get_student_status(student_id_str)
        
        if not student:
            return False, "Student not found", None
            
        if status == 'outside':
            return False, "Not checked in", None
            
        # Update last log
        last_log.check_out = datetime.now()
        try:
            db.session.commit()
            return True, "Check-out successful", last_log
        except Exception as e:
            db.session.rollback()
            return False, f"Database error: {str(e)}", None
