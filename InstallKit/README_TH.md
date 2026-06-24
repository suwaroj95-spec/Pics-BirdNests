# ชุดติดตั้งเครื่องมือสำหรับโปรเจกต์คัดแยกรังนก

ชุดนี้ติดตั้งเฉพาะเครื่องมือที่จำเป็นกับ pipeline ปัจจุบัน เพื่อไม่ให้หนักเครื่องเกินไป:

- `numpy`, `opencv-python`: อ่านภาพและคำนวณ feature
- `pandas`: เปิด/ตรวจ CSV ได้สะดวก
- `scikit-learn`: baseline model, metric, split data, confusion matrix
- `matplotlib`, `pillow`: ทำกราฟและจัดการภาพ
- `streamlit`: ทำหน้า dashboard/review อย่างง่ายในเฟสถัดไป
- `tqdm`: progress bar สำหรับงานประมวลผลจำนวนมาก

## ติดตั้งจาก network ที่ทำงาน

เปิด PowerShell ที่ root โปรเจกต์ แล้วรัน:

```powershell
.\InstallKit\install_project_tools.ps1
```

หลังติดตั้ง เปิด panel ได้ด้วย:

```powershell
.\.venv\Scripts\python.exe project_panel.py --open
```

## ทำชุด wheelhouse ไว้ติดตั้งภายหลัง

เมื่อมี network ให้รัน:

```powershell
.\InstallKit\make_wheelhouse.ps1
```

เมื่อต้อง install แบบไม่ใช้ internet ให้ copy โฟลเดอร์ `wheelhouse` มาพร้อมโปรเจกต์ แล้วรัน:

```powershell
.\InstallKit\install_project_tools.ps1 -FromWheelhouse -Wheelhouse .\wheelhouse
```

## ตัวเลือกเสริม

ถ้าต้องการระบบ label/review เต็มรูปแบบ:

```powershell
.\InstallKit\install_project_tools.ps1 -WithAnnotation
```

ถ้าต้องการ track experiment/model version:

```powershell
.\InstallKit\install_project_tools.ps1 -WithTracking
```

## หมายเหตุเรื่องการใช้งานเชิงพาณิชย์

แพ็กเกจ core เป็น open-source ที่เหมาะกับงานวิจัยและต่อยอดเชิงพาณิชย์โดยทั่วไป แต่ก่อนส่งมอบงานขายจริงควร export รายการ license จาก environment อีกครั้งด้วยคำสั่ง:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-licenses
.\.venv\Scripts\python.exe -m piplicenses --format=markdown --output-file THIRD_PARTY_LICENSES.md
```

ยังไม่ใส่ PyTorch และ Anomalib ในชุด core เพราะหนักกว่า pipeline ปัจจุบันมาก ควรเพิ่มในเฟส deep learning หลังจากมี label ระดับ 70%, 80%, 90% เพียงพอแล้ว
