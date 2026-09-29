import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.tables import Device, NormalizedField
from app.ingestion.vendor_detect import detect_vendor

router = APIRouter(prefix="/devices", tags=["devices"])

@router.post("/upload")
async def upload_devices(
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    created_devices = []
    for file in files:
        content_bytes = await file.read()
        raw_config = content_bytes.decode("utf-8", errors="replace")

        detection = detect_vendor(raw_config)

        # Phase 5: Compute a stable content hash to detect duplicate uploads.
        from app.parsers import engine as pack_engine
        chash = pack_engine.config_hash(raw_config, pack_name=detection.os_hint)

        # Check if an identical config already exists
        existing = session.exec(
            select(Device).where(Device.config_hash == chash)
        ).first()

        if existing:
            created_devices.append({
                "id": str(existing.id),
                "filename": existing.filename,
                "vendor": existing.vendor,
                "os_hint": existing.os_hint,
                "detection_confidence": existing.detection_confidence,
                "uploaded_at": existing.uploaded_at.isoformat(),
                "duplicate": True,
            })
            continue

        device = Device(
            filename=file.filename or "uploaded_config.txt",
            vendor=detection.vendor,
            os_hint=detection.os_hint,
            detection_confidence=detection.confidence,
            raw_config=raw_config,
            config_hash=chash,
        )
        session.add(device)
        session.commit()
        session.refresh(device)

        created_devices.append({
            "id": str(device.id),
            "filename": device.filename,
            "vendor": device.vendor,
            "os_hint": device.os_hint,
            "detection_confidence": device.detection_confidence,
            "uploaded_at": device.uploaded_at.isoformat(),
            "duplicate": False,
        })

    return {"uploaded": created_devices}

@router.get("")
def list_devices(session: Session = Depends(get_session)):
    devices = session.exec(select(
        Device.id, Device.filename, Device.vendor, Device.os_hint, 
        Device.detection_confidence, Device.hostname, Device.uploaded_at
    )).all()
    
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "vendor": d.vendor,
            "os_hint": d.os_hint,
            "detection_confidence": d.detection_confidence,
            "hostname": d.hostname,
            "uploaded_at": d.uploaded_at.isoformat()
        }
        for d in devices
    ]

@router.get("/{device_id}")
def get_device(device_id: uuid.UUID, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.get("/{device_id}/fields")
def get_device_fields(device_id: uuid.UUID, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if not device.current_parse_run_id:
        return []

    fields = session.exec(
        select(NormalizedField)
        .where(NormalizedField.device_id == device_id)
        .where(NormalizedField.parse_run_id == device.current_parse_run_id)
    ).all()
    return fields

@router.post("/seed-samples")
def seed_sample_devices(session: Session = Depends(get_session)):
    sample_configs = [
        (
            "cisco_core_router_01.cfg",
            """Building configuration...
Current configuration : 1820 bytes
!
version 15.2
service timestamps debug datetime msec
service timestamps log datetime msec
hostname CORE-RTR-01
!
ip domain name company.corp
ip name-server 8.8.8.8
!
interface GigabitEthernet0/0
 description WAN-Uplink
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/1
 description LAN-Inside
 ip address 10.0.0.1 255.255.255.0
 no shutdown
!
line vty 0 4
 transport input ssh
 login local
!
banner motd ^C Authorized Access Only ^C
!
ntp server 10.0.0.50
!
end
"""
        ),
        (
            "juniper_edge_srx.conf",
            """system {
    host-name EDGE-SRX-01;
    domain-name internal.corp;
    time-zone UTC;
    services {
        ssh {
            protocol-version v2;
        }
    }
    ntp {
        server 10.0.0.50;
    }
}
interfaces {
    ge-0/0/0 {
        unit 0 {
            family inet {
                address 198.51.100.1/24;
            }
        }
    }
    ge-0/0/1 {
        unit 0 {
            family inet {
                address 10.10.0.1/24;
            }
        }
    }
}
"""
        ),
        (
            "arista_eos_switch_01.cfg",
            """! device: CORE-SW-01 (DCS-7050CX3-32S, EOS-4.28.3M)
!
! boot system flash:/EOS-4.28.3M.swi
!
hostname CORE-SW-01
!
dns domain company.corp
!
ntp server 10.0.0.50
!
no aaa root
!
username admin privilege 15 role network-admin secret sha512 $6$randomhash
!
management api http-commands
   no protocol http
   protocol https
!
management ssh
   idle-timeout 10
   authentication mode keyboard-interactive
!
service routing protocols model multi-agent
!
vrf instance MGMT
!
transceiver qsfp default-mode 4x10G
!
interface Management0
   vrf MGMT
   ip address 10.0.0.10/24
!
interface Ethernet1
   description Uplink-To-Core
   no switchport
   ip address 192.168.1.2/30
!
interface Ethernet2
   description Server-Farm
   switchport mode access
   switchport access vlan 100
!
ip routing
!
end
"""
        ),
    ]

    created = []
    for filename, raw_config in sample_configs:
        detection = detect_vendor(raw_config)
        device = Device(
            filename=filename,
            vendor=detection.vendor,
            os_hint=detection.os_hint,
            detection_confidence=detection.confidence,
            raw_config=raw_config,
        )
        session.add(device)
        session.commit()
        session.refresh(device)
        created.append(device)
    
    return {"message": "Sample devices seeded successfully", "devices": created}

