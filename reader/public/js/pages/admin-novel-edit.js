/* Admin novel edit page. Loaded lazily from admin.js. */

window.AdminNovelEditPage = {
  async render(params) {
    const page = Ui.$('page-admin-novel-edit');
    if (!page) return;
    const slug = params.slug;
    let novel = null;
    try {
      const novels = await Api.getNovels();
      novel = novels.find(n => n.slug === slug);
      page.innerHTML =
        '<div class="c-container">' + Ui.adminNav('novels') +
        '<div class="c-section__header c-admin-page__header c-admin-edit__header">' +
        '<div><h3 class="c-section__title">แก้ไขนิยาย: ' + Ui.esc(slug || '') + '</h3><p class="u-text-muted">แก้ metadata และปก จากนั้นไปจัดตอนหรือนำเข้าต้นฉบับต่อได้ทันที</p></div>' +
        '<div class="c-admin-edit__quick-actions">' +
        '<a class="c-btn c-btn--sm c-btn--ghost" href="#admin/novels" data-nav>' + Ui.icon('library', 'xs') + '<span>รายการนิยาย</span></a>' +
        '<a class="c-btn c-btn--sm c-btn--secondary" href="#novel/' + Ui.esc(slug || '') + '" data-nav>' + Ui.icon('book', 'xs') + '<span>อ่าน</span></a>' +
        '<a class="c-btn c-btn--sm c-btn--secondary" href="#admin/chapters/' + Ui.esc(slug || '') + '" data-nav>' + Ui.icon('bookmarks', 'xs') + '<span>จัดตอน</span></a>' +
        '<a class="c-btn c-btn--sm c-btn--secondary" href="#admin/import/' + Ui.esc(slug || '') + '" data-nav>' + Ui.icon('info', 'xs') + '<span>สุขภาพนำเข้า</span></a>' +
        '</div></div>' +
        '<div class="c-admin-edit-layout">' +
        '<div class="c-admin-cover-panel"><div class="c-admin-cover-preview" id="edit-cover-preview">' + Ui.coverHtml(novel || { slug }) + '</div>' +
        '<input class="c-admin-cover-input" id="edit-cover-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif">' +
        '<div class="c-admin-cover-actions"><button class="c-btn c-btn--primary" id="edit-cover-save" type="button">' + Ui.icon('book', 'xs') + '<span>บันทึกปก</span></button><button class="c-btn c-btn--ghost" id="edit-cover-delete" type="button">' + Ui.icon('close', 'xs') + '<span>ลบปก</span></button></div>' +
        '<span id="edit-cover-status" class="c-admin-edit__status"></span></div>' +
        '<div class="c-settings-form c-admin-edit-form"><div class="c-form">' +
        '<div class="c-form__group"><label class="c-form__label" for="edit-translated-title">ชื่อไทย</label><input class="c-form__input" id="edit-translated-title" value="' + Ui.esc(novel?.translatedTitle || '') + '" /></div>' +
        '<div class="c-form__group"><label class="c-form__label" for="edit-title">ชื่อต้นฉบับ</label><input class="c-form__input" id="edit-title" value="' + Ui.esc(novel?.title || '') + '" /></div>' +
        '<div class="c-form__group"><label class="c-form__label" for="edit-author">ผู้แต่ง</label><input class="c-form__input" id="edit-author" value="' + Ui.esc(novel?.author || '') + '" /></div>' +
        '<div class="c-form__group c-admin-edit__actions"><button class="c-btn c-btn--primary" id="edit-save" type="button">' + Ui.icon('settings', 'xs') + '<span>บันทึก metadata</span></button><span id="edit-status" class="c-admin-edit__status"></span></div>' +
        '</div></div></div></div>';
    } catch (_) {
      Ui.showError(page, 'เกิดข้อผิดพลาด');
    }

    const saveBtn = document.getElementById('edit-save');
    const statusEl = document.getElementById('edit-status');
    if (saveBtn && statusEl) {
      saveBtn.onclick = async () => {
        const title = document.getElementById('edit-title')?.value?.trim() || '';
        const translatedTitle = document.getElementById('edit-translated-title')?.value?.trim() || '';
        const author = document.getElementById('edit-author')?.value?.trim() || '';
        AdminUi.setStatus('edit-status', 'c-admin-edit__status', 'กำลังบันทึก...', 'muted');
        try {
          const res = await fetch('/api/novel/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug, title, author, translatedTitle }),
          });
          const data = await res.json();
          if (res.ok) {
            Api.invalidateAll(slug);
            AdminUi.setStatus('edit-status', 'c-admin-edit__status', 'บันทึกสำเร็จ', 'success');
            Ui.showToast('บันทึกข้อมูลนิยายแล้ว');
          } else {
            AdminUi.setStatus('edit-status', 'c-admin-edit__status', data.error?.message || 'เกิดข้อผิดพลาด', 'error');
          }
        } catch (e) {
          AdminUi.setStatus('edit-status', 'c-admin-edit__status', e.message, 'error');
        }
      };
    }

    const coverInput = document.getElementById('edit-cover-file');
    const coverSaveBtn = document.getElementById('edit-cover-save');
    const coverDeleteBtn = document.getElementById('edit-cover-delete');
    const coverPreview = document.getElementById('edit-cover-preview');
    const coverPanel = coverPreview?.closest('.c-admin-cover-panel');
    let selectedCoverData = '';

    const resizeCoverImage = (file) => new Promise((resolve, reject) => {
      if (!file.type.startsWith('image/')) {
        reject(new Error('ไฟล์นี้ไม่ใช่รูปภาพ'));
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const maxW = 900;
          const scale = Math.min(1, maxW / Math.max(1, img.naturalWidth));
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
          canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            resolve(String(reader.result || ''));
            return;
          }
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL('image/webp', 0.86));
        };
        img.onerror = () => reject(new Error('อ่านรูปไม่สำเร็จ'));
        img.src = String(reader.result || '');
      };
      reader.onerror = () => reject(new Error('อ่านไฟล์รูปไม่สำเร็จ'));
      reader.readAsDataURL(file);
    });

    const readSelectedCover = () => new Promise((resolve, reject) => {
      const file = coverInput?.files?.[0];
      if (!file) {
        reject(new Error('กรุณาเลือกรูปปกก่อนค่ะ'));
        return;
      }
      if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)) {
        reject(new Error('รองรับเฉพาะ PNG, JPEG, WebP หรือ GIF'));
        return;
      }
      if (file.size > 4 * 1024 * 1024) {
        reject(new Error('รูปปกต้องไม่เกิน 4 MB'));
        return;
      }
      resizeCoverImage(file).then(resolve).catch(reject);
    });

    if (coverInput && coverPreview) {
      coverInput.addEventListener('change', async () => {
        try {
          selectedCoverData = await readSelectedCover();
          coverPreview.innerHTML = '<img class="c-cover-img" src="' + Ui.esc(selectedCoverData) + '" alt="Cover preview">';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'พร้อมบันทึกปกใหม่', 'muted');
        } catch (err) {
          selectedCoverData = '';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        }
      });
    }

    if (coverPanel && coverInput && coverPreview) {
      ['dragenter', 'dragover'].forEach(type => {
        coverPanel.addEventListener(type, (event) => {
          event.preventDefault();
          coverPanel.classList.add('is-dragging');
        });
      });
      ['dragleave', 'drop'].forEach(type => {
        coverPanel.addEventListener(type, (event) => {
          event.preventDefault();
          coverPanel.classList.remove('is-dragging');
        });
      });
      coverPanel.addEventListener('drop', async (event) => {
        const file = event.dataTransfer?.files?.[0];
        if (!file) return;
        try {
          if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)) {
            throw new Error('รองรับเฉพาะ PNG, JPEG, WebP หรือ GIF');
          }
          if (file.size > 4 * 1024 * 1024) throw new Error('รูปปกต้องไม่เกิน 4 MB');
          selectedCoverData = await resizeCoverImage(file);
          coverPreview.innerHTML = '<img class="c-cover-img" src="' + Ui.esc(selectedCoverData) + '" alt="Cover preview">';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'พร้อมบันทึกปกใหม่', 'muted');
        } catch (err) {
          selectedCoverData = '';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        }
      });
    }

    if (coverSaveBtn) {
      coverSaveBtn.onclick = async () => {
        try {
          coverSaveBtn.disabled = true;
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'กำลังบันทึกปก...', 'muted');
          const imageData = selectedCoverData || await readSelectedCover();
          const res = await Api.saveNovelCover(slug, imageData);
          selectedCoverData = '';
          if (coverPreview) {
            coverPreview.innerHTML = '<img class="c-cover-img" src="' + Ui.esc(res.data.coverImage) + '" alt="Cover preview">';
          }
          if (coverInput) coverInput.value = '';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'บันทึกปกสำเร็จ', 'success');
        } catch (err) {
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        } finally {
          coverSaveBtn.disabled = false;
        }
      };
    }

    if (coverDeleteBtn) {
      coverDeleteBtn.onclick = async () => {
        try {
          coverDeleteBtn.disabled = true;
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'กำลังลบปก...', 'muted');
          await Api.deleteNovelCover(slug);
          selectedCoverData = '';
          if (coverInput) coverInput.value = '';
          if (coverPreview) coverPreview.innerHTML = Ui.coverHtml({ slug, title: novel?.title || slug });
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'ลบปกแล้ว', 'success');
        } catch (err) {
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        } finally {
          coverDeleteBtn.disabled = false;
        }
      };
    }
  },
};
