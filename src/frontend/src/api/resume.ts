const MAX_RESUME_BYTES = 10 * 1024 * 1024
export function validateResume(file: File): void {
  if (!/\.pdf$/i.test(file.name) || (file.type && !['application/pdf', 'application/octet-stream'].includes(file.type))) {
    throw new Error('请选择 PDF 格式的简历。')
  }
  if (!file.size) throw new Error('该文件为空，请重新选择。')
  if (file.size > MAX_RESUME_BYTES) throw new Error('简历文件不能超过 10 MiB。')
}
