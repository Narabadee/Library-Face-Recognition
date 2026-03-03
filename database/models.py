from datetime import datetime, date
from . import db

class Student(db.Model):
    """นักศึกษาที่ลงทะเบียนในระบบ"""
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)  # รหัสนักศึกษา
    name = db.Column(db.String(100), nullable=False)  # ชื่อ-นามสกุล
    face_encoding_path = db.Column(db.String(255))  # Path to face encoding file
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    attendance_logs = db.relationship('AttendanceLog', backref='student', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Student {self.student_id}: {self.name}>'


class AttendanceLog(db.Model):
    """บันทึกการเข้า-ออกห้องสมุด"""
    __tablename__ = 'attendance_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)  # เวลาเข้า
    check_out = db.Column(db.DateTime, nullable=True)  # เวลาออก (nullable = ยังไม่ออก)
    date = db.Column(db.Date, default=date.today)  # วันที่
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else None,
            'student_code': self.student.student_id if self.student else None,
            'check_in': self.check_in.strftime('%H:%M:%S') if self.check_in else None,
            'check_out': self.check_out.strftime('%H:%M:%S') if self.check_out else None,
            'date': self.date.isoformat() if self.date else None,
            'duration': self._calculate_duration()
        }
    
    def _calculate_duration(self):
        """คำนวณระยะเวลาที่อยู่ในห้องสมุด"""
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f'{hours}h {minutes}m'
        return None
    
    def __repr__(self):
        return f'<AttendanceLog {self.student_id} @ {self.date}>'
