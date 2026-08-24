"""
Email HTML and plain text templates for Clinica Healthcare notifications.
"""

def _base_html_layout(title: str, preheader: str, content_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f8fafc;
      color: #1e293b;
    }}
    .wrapper {{
      max-width: 600px;
      margin: 30px auto;
      background: #ffffff;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
      border: 1px solid #e2e8f0;
    }}
    .header {{
      background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
      padding: 28px 32px;
      text-align: center;
    }}
    .header h1 {{
      margin: 0;
      color: #ffffff;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}
    .header p {{
      margin: 4px 0 0;
      color: #ccfbf1;
      font-size: 13px;
    }}
    .content {{
      padding: 32px;
      line-height: 1.6;
      font-size: 15px;
    }}
    .card {{
      background-color: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      padding: 20px;
      margin: 20px 0;
    }}
    .card-item {{
      margin-bottom: 10px;
    }}
    .card-item:last-child {{
      margin-bottom: 0;
    }}
    .card-label {{
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #64748b;
      margin-bottom: 2px;
    }}
    .card-value {{
      font-size: 15px;
      font-weight: 600;
      color: #0f172a;
    }}
    .alert-danger {{
      background-color: #fef2f2;
      border-left: 4px solid #ef4444;
      padding: 16px;
      border-radius: 8px;
      margin: 20px 0;
      color: #991b1b;
      font-size: 14px;
    }}
    .alert-warning {{
      background-color: #fffbeb;
      border-left: 4px solid #f59e0b;
      padding: 16px;
      border-radius: 8px;
      margin: 20px 0;
      color: #92400e;
      font-size: 14px;
    }}
    .alert-info {{
      background-color: #f0fdf4;
      border-left: 4px solid #10b981;
      padding: 16px;
      border-radius: 8px;
      margin: 20px 0;
      color: #065f46;
      font-size: 14px;
    }}
    .footer {{
      background-color: #f8fafc;
      padding: 24px 32px;
      text-align: center;
      font-size: 12px;
      color: #94a3b8;
      border-top: 1px solid #f1f5f9;
    }}
    .btn {{
      display: inline-block;
      padding: 12px 24px;
      background-color: #0d9488;
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 600;
      border-radius: 8px;
      margin-top: 16px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div style="display:none;font-size:1px;color:#333333;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
    {preheader}
  </div>
  <div class="wrapper">
    <div class="header">
      <h1>Clinïca Health</h1>
      <p>Intelligent Healthcare Portal</p>
    </div>
    <div class="content">
      {content_html}
    </div>
    <div class="footer">
      <p style="margin:0 0 8px;">Clinïca AI Healthcare Platform &bull; Automated Notification System</p>
      <p style="margin:0;">If you have questions, please log in to your patient portal.</p>
    </div>
  </div>
</body>
</html>
"""

def template_appointment_confirmation(
    patient_name: str,
    doctor_name: str,
    specialization: str,
    date_time_str: str,
    symptoms: str,
    appointment_id: str,
) -> tuple[str, str]:
    subject = f"Appointment Confirmed with {doctor_name}"
    plain_text = (
        f"Dear {patient_name},\n\n"
        f"Your appointment has been successfully confirmed.\n\n"
        f"Doctor: {doctor_name} ({specialization})\n"
        f"Date & Time: {date_time_str}\n"
        f"Reason / Symptoms: {symptoms}\n"
        f"Appointment ID: {appointment_id}\n\n"
        f"Please arrive 10 minutes prior to your scheduled consultation time.\n\n"
        f"Best regards,\nClinïca Healthcare Team"
    )

    content_html = f"""
      <h2 style="margin-top:0;color:#0f172a;font-size:18px;">Appointment Confirmed</h2>
      <p>Dear <strong>{patient_name}</strong>,</p>
      <p>Your medical appointment has been successfully booked and confirmed with our clinic.</p>

      <div class="card">
        <div class="card-item">
          <div class="card-label">Doctor</div>
          <div class="card-value">{doctor_name} &bull; <span style="font-weight:normal;color:#64748b;">{specialization}</span></div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Scheduled Date & Time</div>
          <div class="card-value" style="color:#0d9488;">{date_time_str}</div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Reason for Visit</div>
          <div class="card-value" style="font-weight:normal;color:#334155;font-style:italic;">&ldquo;{symptoms}&rdquo;</div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Reference ID</div>
          <div class="card-value" style="font-family:monospace;font-size:13px;color:#64748b;">{appointment_id}</div>
        </div>
      </div>

      <div class="alert-info">
        <strong>Tip:</strong> Please arrive 10 minutes early. You can manage your appointments anytime via your portal.
      </div>
    """
    html = _base_html_layout(subject, f"Your appointment with {doctor_name} on {date_time_str} is confirmed.", content_html)
    return subject, plain_text, html

def template_appointment_cancellation(
    patient_name: str,
    doctor_name: str,
    date_time_str: str,
    reason: str,
    cancelled_by_leave: bool = False,
) -> tuple[str, str]:
    subject = "Appointment Cancelled"
    leave_note = " This was due to doctor approved leave." if cancelled_by_leave else ""
    plain_text = (
        f"Dear {patient_name},\n\n"
        f"Your appointment with {doctor_name} scheduled for {date_time_str} has been cancelled.{leave_note}\n\n"
        f"Reason: {reason or 'No reason specified'}\n\n"
        f"You can reschedule a new consultation at your earliest convenience in the Clinïca portal.\n\n"
        f"Best regards,\nClinïca Healthcare Team"
    )

    content_html = f"""
      <h2 style="margin-top:0;color:#991b1b;font-size:18px;">Appointment Cancelled</h2>
      <p>Dear <strong>{patient_name}</strong>,</p>
      <p>Your scheduled appointment has been cancelled.</p>

      <div class="card">
        <div class="card-item">
          <div class="card-label">Doctor</div>
          <div class="card-value">{doctor_name}</div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Original Date & Time</div>
          <div class="card-value">{date_time_str}</div>
        </div>
      </div>

      <div class="alert-danger">
        <strong>Cancellation Reason:</strong> {reason or "Administrative schedule adjustment"}
      </div>

      <p>We apologize for any inconvenience. Please visit the portal to choose another available slot.</p>
    """
    html = _base_html_layout(subject, f"Your appointment with {doctor_name} has been cancelled.", content_html)
    return subject, plain_text, html

def template_doctor_leave(
    patient_name: str,
    doctor_name: str,
    date_time_str: str,
    leave_period: str,
) -> tuple[str, str]:
    subject = "Appointment Reschedule Notice: Doctor On Leave"
    plain_text = (
        f"Dear {patient_name},\n\n"
        f"We regret to inform you that your appointment with {doctor_name} on {date_time_str} "
        f"has been cancelled because the doctor will be on approved leave ({leave_period}).\n\n"
        f"Please log in to your patient dashboard to choose an alternative appointment slot.\n\n"
        f"Best regards,\nClinïca Healthcare Team"
    )

    content_html = f"""
      <h2 style="margin-top:0;color:#92400e;font-size:18px;">Doctor Leave &bull; Schedule Notice</h2>
      <p>Dear <strong>{patient_name}</strong>,</p>
      <p>We regret to inform you that <strong>{doctor_name}</strong> will be out of office on approved medical/personal leave during <strong>{leave_period}</strong>.</p>

      <div class="alert-warning">
        Your appointment originally scheduled for <strong>{date_time_str}</strong> has been cancelled.
      </div>

      <p>Please log in to your patient dashboard to book a new appointment or consult with another available specialist.</p>
    """
    html = _base_html_layout(subject, f"Notice regarding your appointment with {doctor_name}.", content_html)
    return subject, plain_text, html

def template_appointment_reminder(
    patient_name: str,
    doctor_name: str,
    specialization: str,
    date_time_str: str,
    appointment_id: str,
) -> tuple[str, str]:
    subject = f"Upcoming Appointment Reminder: {doctor_name}"
    plain_text = (
        f"Dear {patient_name},\n\n"
        f"This is a friendly reminder of your upcoming appointment with {doctor_name} ({specialization}).\n\n"
        f"Date & Time: {date_time_str}\n"
        f"Appointment ID: {appointment_id}\n\n"
        f"Please log in to your portal if you need to review pre-visit notes or check details.\n\n"
        f"Best regards,\nClinïca Healthcare Team"
    )

    content_html = f"""
      <h2 style="margin-top:0;color:#0f172a;font-size:18px;">Upcoming Appointment Reminder</h2>
      <p>Dear <strong>{patient_name}</strong>,</p>
      <p>This is a reminder that you have a scheduled appointment coming up soon.</p>

      <div class="card">
        <div class="card-item">
          <div class="card-label">Doctor</div>
          <div class="card-value">{doctor_name} &bull; <span style="font-weight:normal;color:#64748b;">{specialization}</span></div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Date & Time</div>
          <div class="card-value" style="color:#0d9488;">{date_time_str}</div>
        </div>
      </div>

      <div class="alert-info">
        Please make sure you have any previous medical records and your questions ready for the consultation.
      </div>
    """
    html = _base_html_layout(subject, f"Reminder: Your appointment with {doctor_name} is on {date_time_str}.", content_html)
    return subject, plain_text, html

def template_medication_reminder(
    patient_name: str,
    medication_name: str,
    dosage: str,
    dose_label: str,
    instructions: str,
) -> tuple[str, str]:
    subject = f"Medication Reminder: {medication_name}"
    plain_text = (
        f"Dear {patient_name},\n\n"
        f"This is your reminder to take your prescribed medication:\n\n"
        f"Medication: {medication_name} ({dosage})\n"
        f"Dose: {dose_label or 'Scheduled Dose'}\n"
        f"Instructions: {instructions or 'Take as prescribed by doctor'}\n\n"
        f"Best regards,\nClinïca Healthcare Team"
    )

    content_html = f"""
      <h2 style="margin-top:0;color:#0f172a;font-size:18px;">Medication Reminder</h2>
      <p>Dear <strong>{patient_name}</strong>,</p>
      <p>It is time for your scheduled medication dose:</p>

      <div class="card">
        <div class="card-item">
          <div class="card-label">Medication & Dosage</div>
          <div class="card-value" style="color:#0d9488;font-size:17px;">{medication_name} &bull; {dosage}</div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Dose Schedule</div>
          <div class="card-value">{dose_label or "Prescribed Dose"}</div>
        </div>
        <div class="card-item" style="margin-top:12px;">
          <div class="card-label">Doctor's Instructions</div>
          <div class="card-value" style="font-weight:normal;color:#334155;">{instructions or "Take as prescribed."}</div>
        </div>
      </div>

      <p style="font-size:13px;color:#64748b;">If you experience any adverse effects, please contact your doctor immediately.</p>
    """
    html = _base_html_layout(subject, f"Time to take your medication: {medication_name} ({dosage}).", content_html)
    return subject, plain_text, html

def template_password_reset_otp(
    user_name: str,
    otp_code: str,
    expiry_minutes: int = 10,
) -> tuple[str, str, str]:
    """
    Template for sending Password Reset OTP verification code.
    Returns: (subject, plain_text_body, html_body)
    """
    subject = f"Your Password Reset Code: {otp_code} - Clinica Healthcare"

    plain_text = (
        f"Hello {user_name},\n\n"
        f"You recently requested to reset your password for your Clinica account.\n\n"
        f"Your 6-Digit Verification Code (OTP) is: {otp_code}\n\n"
        f"This code will expire in {expiry_minutes} minutes. "
        f"If you did not request this password reset, please ignore this email or contact support.\n\n"
        f"Clinica Healthcare Team"
    )

    content_html = f"""
      <h2 style="margin-top:0;color:#0f172a;font-size:18px;">Password Reset Request</h2>
      <p>Hello <strong>{user_name}</strong>,</p>
      <p>We received a request to reset the password for your <strong>Clinica</strong> account. Use the one-time verification code below to proceed:</p>

      <div style="background: linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%); border: 2px dashed #0d9488; border-radius: 16px; padding: 24px; text-align: center; margin: 24px 0;">
        <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #0f766e; margin-bottom: 8px;">One-Time Verification Code</div>
        <div style="font-size: 38px; font-weight: 800; letter-spacing: 8px; color: #0f766e; font-family: monospace;">{otp_code}</div>
        <div style="font-size: 12px; color: #64748b; margin-top: 8px;">Expires in {expiry_minutes} minutes &bull; Never share this code with anyone</div>
      </div>

      <p style="font-size: 13px; color: #64748b;">If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
    """

    html = _base_html_layout(
        title="Reset Your Clinica Password",
        preheader=f"Your verification code is {otp_code}. Valid for {expiry_minutes} minutes.",
        content_html=content_html,
    )
    return subject, plain_text, html

