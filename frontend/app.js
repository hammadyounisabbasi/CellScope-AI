const state = { image: null, experiment: null, assistant: null };
const $ = selector => document.querySelector(selector);

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); }
  catch { throw new Error('Server returned an unreadable response.'); }
  if (!response.ok) throw new Error(data.detail || 'Request failed.');
  return data;
}

function busy(form, active, label) {
  const button = form.querySelector('button');
  if (active) {
    button.dataset.text = button.textContent;
    button.textContent = label;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.text;
    button.disabled = false;
  }
}

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = String(value);
  return element.innerHTML;
}

function fileDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Could not preview the selected file.'));
    reader.readAsDataURL(file);
  });
}

api('/health')
  .then(() => {
    $('#api-status').textContent = 'API ONLINE';
    $('#api-status').style.color = '#2dd4bf';
  })
  .catch(() => { $('#api-status').textContent = 'API OFFLINE'; });

$('#image-form').addEventListener('submit', async event => {
  event.preventDefault();
  const file = $('#image-file').files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  busy(event.target, true, 'Analyzing...');
  $('#image-state').textContent = 'Processing';
  try {
    const original = await fileDataUrl(file);
    state.image = await api('/api/images/analyze', { method: 'POST', body: formData });
    const result = state.image;
    const metrics = result.metrics;
    $('#image-state').textContent = `${metrics.object_count} objects detected`;
    $('#image-visuals').classList.remove('empty');
    $('#image-visuals').innerHTML = `
      <figure><img src="${original}" alt="Uploaded microscopy image"><figcaption>Original</figcaption></figure>
      <figure><img src="data:image/png;base64,${result.overlay_png_base64}" alt="Segmentation overlay"><figcaption>Overlay</figcaption></figure>
      <figure><img src="data:image/png;base64,${result.mask_png_base64}" alt="Binary foreground mask"><figcaption>Mask</figcaption></figure>`;
    $('#image-metrics').innerHTML = [
      ['Objects', metrics.object_count],
      ['Mean area', metrics.mean_area_px],
      ['Perimeter', metrics.mean_perimeter_px],
      ['Circularity', metrics.mean_circularity],
      ['Eccentricity', metrics.mean_eccentricity],
      ['Intensity', metrics.mean_intensity],
      ['Foreground', metrics.foreground_fraction],
      ['Focus', metrics.focus_score],
    ].map(([key, value]) => `<div class="metric"><b>${escapeHtml(value)}</b><small>${key}</small></div>`).join('');
    const notes = result.reliability.notes.map(note => escapeHtml(note)).join('<br>');
    $('#image-reliability').classList.remove('empty');
    $('#image-reliability').innerHTML = `<b>${escapeHtml(result.method)}</b><br><small>${notes}</small>`;
    toast('Microscopy analysis complete');
  } catch (error) {
    $('#image-state').textContent = 'Analysis failed';
    toast(error.message);
  } finally { busy(event.target, false); }
});

$('#csv-form').addEventListener('submit', async event => {
  event.preventDefault();
  const file = $('#csv-file').files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  busy(event.target, true, 'Analyzing...');
  $('#csv-state').textContent = 'Processing';
  try {
    state.experiment = await api('/api/experiments/analyze', { method: 'POST', body: formData });
    const result = state.experiment;
    const schema = result.schema_summary;
    $('#csv-state').textContent = `${result.rows} rows / ${result.columns} columns`;
    const schemaSummary = `<div class="finding"><b>Detected schema</b><br><small>` +
      `Numeric: ${schema.numeric_columns.map(escapeHtml).join(', ') || 'none'}<br>` +
      `Categorical: ${schema.categorical_columns.map(escapeHtml).join(', ') || 'none'}<br>` +
      `Candidate group: ${escapeHtml(schema.group_column || 'not inferred')}<br>` +
      `Missing values: ${escapeHtml(JSON.stringify(schema.missing_values))}</small></div>`;
    const findings = result.group_comparisons.slice(0, 8).map(item =>
      `<div class="finding"><b>${escapeHtml(item.feature)}</b> / d=${escapeHtml(item.cohens_d)} / p=${escapeHtml(item.p_value_unadjusted)}` +
      `<br><small>${escapeHtml(item.control_label)}: ${escapeHtml(item.control_mean)} / ${escapeHtml(item.treatment_label)}: ${escapeHtml(item.treatment_mean)}` +
      `<br>Exploratory association; not a causal conclusion.</small></div>`).join('');
    const correlations = result.correlations.slice(0, 5).map(item =>
      `<div class="finding"><b>${escapeHtml(item.left)} vs ${escapeHtml(item.right)}</b>` +
      `<br><small>Spearman rho=${escapeHtml(item.spearman_rho)}; correlation does not establish causality.</small></div>`).join('');
    const charts = result.charts.map(chart =>
      `<img src="data:image/png;base64,${chart.png_base64}" alt="${escapeHtml(chart.title)}">`).join('');
    $('#csv-results').classList.remove('empty');
    $('#csv-results').innerHTML = `${schemaSummary}<p>${result.observations.map(escapeHtml).join('<br>')}</p>` +
      `${findings || '<p>No two-group comparison was available.</p>'}${correlations}${charts}`;
    toast('Experiment analysis complete');
  } catch (error) {
    $('#csv-state').textContent = 'Analysis failed';
    toast(error.message);
  } finally { busy(event.target, false); }
});

$('#chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  const question = $('#question').value;
  const log = $('#chat-log');
  log.insertAdjacentHTML('beforeend', `<div class="message user"><b>You</b><p>${escapeHtml(question)}</p></div>`);
  busy(event.target, true, 'Thinking...');
  try {
    state.assistant = await api('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, image_analysis: state.image, experiment_analysis: state.experiment }),
    });
    const result = state.assistant;
    const sources = result.sources.map(source =>
      `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">[${escapeHtml(source.id)}] ${escapeHtml(source.title)}</a>`).join('');
    const trace = result.workflow_trace.map(step => step.node).join(' -> ');
    log.insertAdjacentHTML('beforeend', `<div class="message"><b>CellScope</b><p>${escapeHtml(result.answer)}</p>` +
      `<div class="sources">${sources}</div><small>Workflow: ${escapeHtml(trace)}</small></div>`);
    $('#question').value = '';
    log.lastElementChild.scrollIntoView({ behavior: 'smooth' });
  } catch (error) { toast(error.message); }
  finally { busy(event.target, false); }
});

$('#report-button').addEventListener('click', async () => {
  if (!state.image && !state.experiment) {
    toast('Run an analysis before generating a report.');
    return;
  }
  try {
    const result = await api('/api/reports/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'CellScope AI Experiment Report',
        image_analysis: state.image,
        experiment_analysis: state.experiment,
        assistant_answer: state.assistant,
      }),
    });
    const blob = new Blob([result.html], { type: result.content_type });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = result.filename;
    link.click();
    URL.revokeObjectURL(link.href);
    toast('Report generated');
  } catch (error) { toast(error.message); }
});
