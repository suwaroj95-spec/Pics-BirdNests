# Export The Print Handbook To PDF

คู่มือ PDF ใน phase นี้สร้างจาก browser เท่านั้น ไม่ commit binary PDF เข้า repository

## Windows Microsoft Edge

1. Build documentation:

   ```powershell
   .\tools\build_documentation.ps1
   ```

2. Open:

   ```text
   docs/manual/print-handbook.html
   ```

3. In Microsoft Edge, press `Ctrl+P`.

4. Set printer to `Save as PDF`.

5. Set layout to `Portrait`.

6. Enable `Background graphics` if diagrams or colored callouts are needed.

7. Confirm destination filename outside generated source folders, for example:

   ```text
   BirdNests-Technical-Handbook.pdf
   ```

8. Click `Save`.

Do not use external PDF services for project data or screenshots.
