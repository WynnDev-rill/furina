function openImageEditor(){
  if(selectedAttachment?.kind!=='image')return;
  if(!NATIVE?.editImage){toast('Editor native hanya tersedia di APK terbaru.');return}
  NATIVE.editImage(selectedAttachment.base64,selectedAttachment.name,selectedAttachment.mime);
}
