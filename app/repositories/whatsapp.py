from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import ClientEmployee
from app.models.whatsapp import WhatsAppGroup, WhatsAppUser


class WhatsAppRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_group_by_external_id(self, group_id: str) -> WhatsAppGroup | None:
        return self.db.scalar(select(WhatsAppGroup).where(WhatsAppGroup.group_id == group_id))

    def upsert_user(self, group: WhatsAppGroup, phone: str, name: str | None) -> WhatsAppUser:
        employee = self.db.scalar(
            select(ClientEmployee).where(
                ClientEmployee.whatsapp_group_id == group.id,
                ClientEmployee.phone == phone,
                ClientEmployee.is_active.is_(True),
            )
        )
        user = self.db.scalar(
            select(WhatsAppUser).where(
                WhatsAppUser.group_id == group.id,
                WhatsAppUser.phone == phone,
            )
        )
        if user is None:
            user = WhatsAppUser(
                group=group,
                phone=phone,
                name=name or (employee.name if employee else None),
                employee=employee,
            )
            self.db.add(user)
        else:
            if name and user.name != name:
                user.name = name
            elif employee and not user.name:
                user.name = employee.name
            if user.employee_id != (employee.id if employee else None):
                user.employee = employee
        return user
