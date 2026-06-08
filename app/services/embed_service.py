import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.tenant_filter import TenantQuery
from app.models.embed_form import EmbedFormConfig
from app.models.mailing_list import MailingList
from app.schemas.embed_form import EmbedFormConfigCreate
from app.services.audit_service import AuditService


class EmbedService:
    def __init__(self, session: AsyncSession, tq: TenantQuery, audit: AuditService):
        self.session = session
        self.tq = tq
        self.audit = audit

    async def create_config(self, data: EmbedFormConfigCreate) -> EmbedFormConfig:
        await self.tq.get_or_404(MailingList, data.list_id)

        config = EmbedFormConfig(
            tenant_id=self.tq.tenant_id,
            list_id=data.list_id,
            allowed_domains=data.allowed_domains,
            honeypot_field_name=data.honeypot_field_name,
            captcha_enabled=data.captcha_enabled,
            captcha_provider=data.captcha_provider,
            captcha_site_key=data.captcha_site_key,
            captcha_secret_key=data.captcha_secret_key,
            rate_limit_per_ip=data.rate_limit_per_ip,
            custom_css=data.custom_css,
            redirect_url=data.redirect_url,
        )
        self.session.add(config)
        await self.session.flush()
        await self.audit.log("create", "embed_form_config", config.id)
        await self.session.commit()
        return config

    async def get_config(self, config_id: uuid.UUID) -> EmbedFormConfig:
        return await self.tq.get_or_404(EmbedFormConfig, config_id)

    async def generate_embed_code(self, config_id: uuid.UUID) -> str:
        config = await self.tq.get_or_404(EmbedFormConfig, config_id)
        mailing_list = await self.tq.get_or_404(MailingList, config.list_id)

        api_url = settings.public_api_url
        form_id = str(config.id).replace("-", "")

        captcha_html = ""
        captcha_script = ""
        if config.captcha_enabled and config.captcha_site_key:
            if config.captcha_provider == "recaptcha":
                captcha_script = '<script src="https://www.google.com/recaptcha/api.js" async defer></script>'
                captcha_html = f'<div class="g-recaptcha" data-sitekey="{config.captcha_site_key}"></div>'
            elif config.captcha_provider == "turnstile":
                captcha_script = '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
                captcha_html = f'<div class="cf-turnstile" data-sitekey="{config.captcha_site_key}"></div>'

        custom_style = f"<style>{config.custom_css}</style>" if config.custom_css else ""

        html = f"""<!-- MailGenius Subscribe Form: {mailing_list.name} -->
{captcha_script}
{custom_style}
<div id="mg-form-{form_id}">
  <form id="mg-subscribe-{form_id}" method="POST" action="{api_url}/api/v1/subscription/subscribe">
    <input type="hidden" name="list_id" value="{config.list_id}" />
    <input type="hidden" name="tenant_id" value="{config.tenant_id}" />
    <input type="email" name="email" placeholder="Your email" required />
    <input type="text" name="name" placeholder="Your name" />
    <div style="position:absolute;left:-9999px;" aria-hidden="true">
      <input type="text" name="{config.honeypot_field_name}" tabindex="-1" autocomplete="off" />
    </div>
    {captcha_html}
    <button type="submit">Subscribe</button>
  </form>
  <div id="mg-msg-{form_id}" style="display:none;"></div>
</div>
<script>
(function(){{
  var form=document.getElementById('mg-subscribe-{form_id}');
  var msg=document.getElementById('mg-msg-{form_id}');
  form.addEventListener('submit',function(e){{
    e.preventDefault();
    if(form.elements['{config.honeypot_field_name}'].value!=='')return;
    var data=new FormData(form);
    fetch(form.action,{{method:'POST',body:data}})
      .then(function(r){{return r.json();}})
      .then(function(d){{msg.textContent=d.message||'Success!';msg.style.display='block';}})
      .catch(function(){{msg.textContent='An error occurred.';msg.style.display='block';}});
  }});
}})();
</script>"""
        return html
