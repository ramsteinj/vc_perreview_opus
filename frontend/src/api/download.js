import client from './client'

/** 응답 헤더의 filename*=UTF-8''... 에서 파일명을 복원한다. */
function parseFilename(disposition, fallback) {
  if (!disposition) return fallback
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1].trim().replace(/^"|"$/g, ''))
    } catch {
      return fallback
    }
  }
  const plain = disposition.match(/filename="?([^";]+)"?/i)
  return plain ? plain[1] : fallback
}

/**
 * 인증이 필요한 파일을 내려받는다.
 *
 * JWT를 Authorization 헤더로 보내므로 <a href>로는 받을 수 없다.
 * blob으로 받아 임시 링크를 만들어 클릭시킨다.
 */
export async function downloadFile(path, { params = {}, fallbackName = 'download.csv' } = {}) {
  const response = await client.get(path, { params, responseType: 'blob' })

  const filename = parseFilename(response.headers['content-disposition'], fallbackName)
  const objectUrl = URL.createObjectURL(response.data)

  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()

  // 즉시 해제하면 일부 브라우저에서 다운로드가 중단된다
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)

  return filename
}

export function downloadCycleCsv(cycleId, kind, params = {}) {
  return downloadFile(`/admin/cycles/${cycleId}/export/${kind}.csv`, {
    params,
    fallbackName: `${kind}.csv`,
  })
}
