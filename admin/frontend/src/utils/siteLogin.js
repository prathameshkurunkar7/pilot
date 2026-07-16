export async function openSiteLogin(createLink) {
  const popup = window.open('', `site-login-${window.crypto.randomUUID()}`)
  if (!popup) throw new Error('Allow pop-ups to open the site.')
  popup.opener = null

  try {
    const link = await createLink()
    if (typeof link?.url !== 'string') {
      throw new Error('The site login link is invalid.')
    }
    popup.location = link.url
    return link
  } catch (error) {
    popup.close()
    throw error
  }
}
