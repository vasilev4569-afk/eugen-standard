---
title: "Samsung T7 1TB – Raw Test Data"
description: "Independent raw performance measurements for Samsung T7 1TB."
---



{{< rawhtml >}}

<style>
.meta-table, .data-table { width:100%; border-collapse: collapse; margin: 10px 0,0 18px; }
.meta-table th, .meta-table td, .data-table th, .data-table td { border:1px solid #e1e1e1; padding:10px; text-align:left; vertical-align:top; }
.meta-table th, .data-table th { background:#f6f6f6; }
.kpi { font-weight:700; }
.note { background:#fafafa; border:1px solid #eee; padding:12px; border-radius:12px; }
</style>

<section aria-label="Samsung T7 1TB data">

  <h2>Test unit & environment</h2>
  <table class="meta-table">
    <tbody>
      <tr><th>SSD model</th><td>Samsung Portable SSD T7</td></tr>
      <tr><th>Capacity (GiB)</th><td>931</td></tr>
      <tr><th>Serial number</th><td>S7MENS0Y511580A</td></tr>
      <tr><th>Firmware</th><td>FXG44P2Q</td></tr>
      <tr><th>Operating system</th><td>Windows 10</td></tr>
      <tr><th>Fio version</th><td>3</td></tr>
    </tbody>
  </table>

  <h2>1) Fresh Sequential Write (250GiB)</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Metric</th>
        <th>Attempt 1<br><small>2026-2-13</small></th>
        <th>Attempt 2<br><small>2026-2-14</small></th>
        <th>Attempt 3<br><small>2026-2-15</small></th>
        <th>Average</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Avg Speed (MB/s)</td><td>516</td><td>515</td><td>503</td><td class="kpi">511</td></tr>
      <tr><td>Sustained Speed (MB/s)</td><td>482</td><td>482</td><td>470</td><td class="kpi">478</td></tr>
      <tr><td>SLC Speed (MB/s)</td><td>780</td><td>779</td><td>745</td><td class="kpi">768</td></tr>
      <tr><td>Time SLC (sec)</td><td>60</td><td>59</td><td>63</td><td class="kpi">61</td></tr>
      <tr><td>GiB (SLC data)</td><td>44</td><td>43</td><td>44</td><td class="kpi">44</td></tr>
      <tr><td>Time total (sec)</td><td>520</td><td>521</td><td>524</td><td class="kpi">522</td></tr>
    </tbody>
  </table>

  <h2>2) Sequential Read (250GiB)</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Metric</th>
        <th>Attempt 1<br><small>2026-1-28</small></th>
        <th>Attempt 2<br><small>2026-1-28</small></th>
        <th>Attempt 3<br><small>2026-1-28</small></th>
        <th>Average</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Avg Speed (MB/s)</td><td>658</td><td>651</td><td>662</td><td class="kpi">657</td></tr>
      <tr><td>Data Size (GiB)</td><td>184</td><td>182</td><td>185</td><td class="kpi">184</td></tr>
    </tbody>
  </table>

  <h2>3) Random Read 4K QD1</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Metric</th>
        <th>Attempt 1<br><small>2026-2-8</small></th>
        <th>Attempt 2<br><small>2026-2-8</small></th>
        <th>Attempt 3<br><small>2026-2-8</small></th>
        <th>Average</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Avg Speed (MB/s)</td><td>11</td><td>12</td><td>12</td><td class="kpi">12</td></tr>
      <tr><td>Latency p99 (ms)</td><td>0,5</td><td>0,5</td><td>0,5</td><td class="kpi">0,5</td></tr>
      <tr><td>Latency p99.9 (ms)</td><td>0,5</td><td>0,5</td><td>0,5</td><td class="kpi">0,5</td></tr>
    </tbody>
  </table>

  <p class="note">
    <strong>Method notes:</strong> standardized 250 GiB workload, results shown per attempt and averaged.
    Full methodology: <a href="/en/methodology/">/en/methodology/</a>
  </p>

</section>

{{< /rawhtml >}}


