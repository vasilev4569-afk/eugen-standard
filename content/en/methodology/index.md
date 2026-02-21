---
title: "Methodology"
description: "Standardized performance testing methodology used by Eugen Standard."
---

## Core Principles

Eugen Standard publishes raw, repeatable performance measurements.

- No sponsorship influence
- No subjective scores
- No composite ratings
- All attempts are published
- All tests follow fixed procedural rules

The objective is strict comparability across devices.

---

## Test Environment

Each device is tested under documented and controlled conditions.

For every published unit, the following parameters are disclosed:

- Model
- Capacity (GiB)
- Serial number (partially masked)
- Firmware version
- Operating system
- Fio version

### Environmental Conditions

- Room temperature: 21–24°C
- Identical hardware platform
- No background workloads
- Fixed software versions

All tests are executed using Fio under Windows with:

- ioengine=windowsaio
- direct=1 (OS cache bypassed)
- numjobs=1

Each scenario is executed three times.

---

# External SSD Test Scenarios

## 1. Fresh Sequential Write — 250 GiB

### Purpose

This test measures:

- Real sustained sequential write performance
- SLC cache behavior
- Post-cache stability
- Total time required to write large data volumes

A 250 GiB workload forces the drive beyond short marketing burst behavior.

### Procedure

1. Before the first attempt, the drive is formatted in Windows using **Quick Format** (file system metadata rebuilt).  
   The file system remains the manufacturer default (e.g. exFAT/NTFS as shipped).  
   Allocation unit size remains the system default.

2. The drive remains in idle state for a minimum of **10 hours** before the first run.  
   Idle means the drive remains powered and connected to the system, with no read or write operations performed and no background workloads running.

3. A 250 GiB sequential write workload is executed.

4. After each attempt, the drive remains in idle state for a minimum of **10 hours** under the same conditions before the next run.

The idle period allows the controller to complete internal background operations
(garbage collection, block consolidation, cache recovery), ensuring comparable starting conditions.

After the final write attempt, the written file remains on the drive for read testing.

### Fio Command (PowerShell)

```powershell
fio --name=Fresh_Sequential_Write `
  --filename=250gb.dat `
  --rw=write `
  --bs=1M `
  --iodepth=1 `
  --direct=1 `
  --ioengine=windowsaio `
  --numjobs=1 `
  --size=250G `
  --write_bw_log=fresh_write_250gb `
  --log_avg_msec=1000 `
  --fallocate=none `
  --output=fresh_write_run.txt
```

Published metrics:

- Avg Speed (MB/s)
- Sustained Speed (MB/s)
- SLC Speed (MB/s)
- Time SLC (sec)
- GiB (SLC data)
- Time total (sec)

---

## 2. Sequential Read — 250 GiB (Single Pass)

### Purpose

This test measures:

- Large file read performance
- Real-world archive / media workloads
- Full-range consistency

The test reads the file created during the final write attempt.

Between read attempts:

- Minimum 1 hour idle period under the same defined idle conditions

### Fio Command (PowerShell)

```powershell
fio --name=Sequential_Read_Single_Pass `
  --filename=250gb.dat `
  --size=250G `
  --rw=read `
  --bs=1M `
  --iodepth=1 `
  --direct=1 `
  --ioengine=windowsaio `
  --numjobs=1 `
  --write_bw_log=sequential_read_single_pass_250gb `
  --log_avg_msec=1000 `
  --log_unix_epoch=1 `
  --thread `
  --output=read_run.txt
```

Published metrics:

- Avg Speed (MB/s)
- Data Size (GiB)

---

## 3. Random Read — 4K QD1

### Purpose

This test measures:

- Small-block access performance
- OS-level responsiveness
- Application launch behavior
- Controller latency handling

Queue depth 1 reflects typical consumer workloads rather than synthetic stress tests.

Between attempts:

- Minimum 1 hour idle period under the same defined idle conditions

### Fio Command (PowerShell)

```powershell
fio --name=Random_Read_4K_QD1 `
  --filename=250gb.dat `
  --rw=randread `
  --bs=4k `
  --iodepth=1 `
  --numjobs=1 `
  --direct=1 `
  --ioengine=windowsaio `
  --time_based=1 `
  --runtime=300 `
  --write_bw_log=es_rr4k_qd1_bw `
  --log_avg_msec=1000 `
  --output=es_rr4k_qd1_run.txt
```

Published metrics:

- Avg Speed (MB/s)
- Latency p99 (ms)

---

## Data Reporting & Processing

- Each scenario is executed three times
- All individual attempts are published
- Median value is used as the primary comparison metric
- No weighting, normalization, or artificial scoring is applied
- All results are derived directly from raw Fio output logs

The methodology is designed to prioritize transparency, repeatability, and cross-device comparability.
