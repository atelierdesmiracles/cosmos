SUMMARY = "COSMOS native Klipper Power Resume checkpoint journal"
DESCRIPTION = "Small opt-in Kalico module that journals virtual SD print state"
LICENSE = "GPL-3.0-only"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-3.0-only;md5=1ebbd3e34237af26da5dc08a4e440464"

SRC_URI = " \
    file://power_resume.py \
    file://power-resume.cfg \
"

S = "${WORKDIR}"

RDEPENDS:${PN} = "kalico python3-core"

do_install() {
    install -d ${D}${datadir}/klipper/klippy/extras
    install -m 0644 ${WORKDIR}/power_resume.py ${D}${datadir}/klipper/klippy/extras/power_resume.py

    install -d ${D}${sysconfdir}/klipper/config/klipper-readonly
    install -m 0644 ${WORKDIR}/power-resume.cfg ${D}${sysconfdir}/klipper/config/klipper-readonly/power-resume.cfg
}

FILES:${PN} += " \
    ${datadir}/klipper/klippy/extras/power_resume.py \
    ${sysconfdir}/klipper/config/klipper-readonly/power-resume.cfg \
"
