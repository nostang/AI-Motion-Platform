// =====================================================
// AI Motion Platform
// Report Page Controller
// =====================================================

document.addEventListener("DOMContentLoaded", async () => {
    const overallScoreElement =
        document.getElementById("overallScore");

    const coachStatusElement =
        document.getElementById("coachStatus");

    const feedbackListElement =
        document.getElementById("feedbackList");

    const radarCanvas =
        document.getElementById("radarChart");

    const backButton =
        document.getElementById("backButton");

    let radarChartInstance = null;

    function getAssessmentId() {
        const queryParameters =
            new URLSearchParams(window.location.search);

        return queryParameters.get("id");
    }

    function setText(element, value) {
        const isEmpty =
            value === null ||
            value === undefined ||
            value === "";

        element.textContent =
            isEmpty
                ? "--"
                : String(value);
    }

    function normalizeStatus(status) {
        if (!status) {
            return "UNKNOWN";
        }

        return String(status)
            .trim()
            .toUpperCase();
    }

    function getStatusLabel(status) {
        const normalizedStatus =
            normalizeStatus(status);

        const labels = {
            PASS: "PASS",
            COMPLETED: "COMPLETED",
            NEEDS_REVIEW: "NEEDS REVIEW",
            FAILED: "FAILED",
            NOT_EVALUATED: "NOT EVALUATED",
            UNKNOWN: "UNKNOWN"
        };

        return (
            labels[normalizedStatus] ||
            normalizedStatus
        );
    }

    function getStatusType(status) {
        const normalizedStatus =
            normalizeStatus(status);

        if (
            normalizedStatus === "PASS" ||
            normalizedStatus === "COMPLETED"
        ) {
            return "success";
        }

        if (
            normalizedStatus === "NEEDS_REVIEW" ||
            normalizedStatus === "NOT_EVALUATED"
        ) {
            return "warning";
        }

        if (normalizedStatus === "FAILED") {
            return "error";
        }

        return "default";
    }

    function renderOverall(report) {
        const overallScore =
            report?.summary?.overall_score;

        if (
            overallScore === null ||
            overallScore === undefined
        ) {
            setText(
                overallScoreElement,
                "Not Evaluated"
            );

            overallScoreElement.dataset.status =
                "warning";

            return;
        }

        setText(
            overallScoreElement,
            overallScore
        );

        overallScoreElement.dataset.status =
            "success";
    }

    function renderCoachStatus(report) {
        const coachStatus =
            report?.summary?.coach_status ||
            "UNKNOWN";

        setText(
            coachStatusElement,
            getStatusLabel(coachStatus)
        );

        coachStatusElement.dataset.status =
            getStatusType(coachStatus);
    }

    function createFeedbackItem(
        title,
        description,
        status = "default"
    ) {
        const listItem =
            document.createElement("li");

        listItem.className =
            "feedback-item";

        listItem.dataset.status =
            status;

        const titleElement =
            document.createElement("strong");

        titleElement.textContent =
            title;

        const descriptionElement =
            document.createElement("span");

        descriptionElement.textContent =
            description;

        listItem.appendChild(
            titleElement
        );

        listItem.appendChild(
            descriptionElement
        );

        return listItem;
    }

    function renderFeedback(report) {
        feedbackListElement.innerHTML = "";

        const feedback =
            Array.isArray(report?.feedback)
                ? report.feedback
                : [];

        const missingDirections =
            Array.isArray(
                report?.observation
                    ?.missing_directions
            )
                ? report.observation
                    .missing_directions
                : [];

        const completed =
            report?.summary?.completed === true;

        const returnCenter =
            report?.observation?.return_center;

        const motionContinuous =
            report?.observation
                ?.motion_continuous;

        if (completed) {
            feedbackListElement.appendChild(
                createFeedbackItem(
                    "Movement completion",
                    "Eight movement events were completed.",
                    "success"
                )
            );
        }

        if (returnCenter === true) {
            feedbackListElement.appendChild(
                createFeedbackItem(
                    "Return to center",
                    "All detected movements returned to the center position.",
                    "success"
                )
            );
        }

        if (motionContinuous === true) {
            feedbackListElement.appendChild(
                createFeedbackItem(
                    "Motion continuity",
                    "The movement sequence was completed continuously.",
                    "success"
                )
            );
        }

        if (missingDirections.length > 0) {
            feedbackListElement.appendChild(
                createFeedbackItem(
                    "Direction coverage needs review",
                    `Missing directions: ${missingDirections.join(", ")}.`,
                    "warning"
                )
            );
        }

        feedback.forEach((item) => {
            if (typeof item === "string") {
                feedbackListElement.appendChild(
                    createFeedbackItem(
                        "Coach feedback",
                        item
                    )
                );

                return;
            }

            if (
                item &&
                typeof item === "object"
            ) {
                const title =
                    item.title ||
                    item.name ||
                    "Coach feedback";

                const description =
                    item.message ||
                    item.description ||
                    item.explanation ||
                    JSON.stringify(item);

                const status =
                    getStatusType(
                        item.status ||
                        item.result
                    );

                feedbackListElement.appendChild(
                    createFeedbackItem(
                        title,
                        description,
                        status
                    )
                );
            }
        });

        if (
            feedbackListElement.children.length === 0
        ) {
            feedbackListElement.appendChild(
                createFeedbackItem(
                    "No coach feedback available",
                    "The current report does not contain additional coach feedback.",
                    "default"
                )
            );
        }
    }

    function normalizeRadarScores(scores) {
        return scores.map((score) => {
            if (
                score === null ||
                score === undefined ||
                Number.isNaN(Number(score))
            ) {
                return null;
            }

            return Number(score);
        });
    }

    function createChartNote(
        rawScores,
        labels
    ) {
        const existingNote =
            document.querySelector(
                ".chart-note"
            );

        if (existingNote) {
            existingNote.remove();
        }

        const notEvaluatedLabels =
            labels.filter(
                (_, index) =>
                    rawScores[index] === null ||
                    rawScores[index] === undefined
            );

        if (notEvaluatedLabels.length === 0) {
            return;
        }

        const note =
            document.createElement("p");

        note.className =
            "chart-note";

        note.textContent =
            "Not evaluated in the current version: " +
            notEvaluatedLabels.join(", ") +
            ". These values are intentionally left blank and are not zero scores.";

        radarCanvas.insertAdjacentElement(
            "afterend",
            note
        );
    }

    function renderRadarChart(report) {
        const labels =
            Array.isArray(
                report?.radar_chart?.labels
            )
                ? report.radar_chart.labels
                : [];

        const rawScores =
            Array.isArray(
                report?.radar_chart?.scores
            )
                ? report.radar_chart.scores
                : [];

        const maximumScore =
            Number(
                report?.radar_chart?.max_score
            ) || 25;

        if (
            labels.length === 0 ||
            rawScores.length === 0
        ) {
            radarCanvas.style.display =
                "none";

            return;
        }

        radarCanvas.style.display =
            "block";

        const normalizedScores =
            normalizeRadarScores(rawScores);

        createChartNote(
            rawScores,
            labels
        );

        if (radarChartInstance) {
            radarChartInstance.destroy();
        }

        radarChartInstance =
            new Chart(
                radarCanvas,
                {
                    type: "radar",

                    data: {
                        labels,

                        datasets: [
                            {
                                label:
                                    "AI Motion Assessment",

                                data:
                                    normalizedScores,

                                borderWidth: 2,

                                pointRadius(context) {
                                    const value =
                                        context.raw;

                                    return value === null
                                        ? 0
                                        : 4;
                                },

                                pointHoverRadius(context) {
                                    const value =
                                        context.raw;

                                    return value === null
                                        ? 0
                                        : 6;
                                },

                                spanGaps: false,

                                fill: true,

                                borderColor:
                                    "rgba(56, 189, 248, 1)",

                                backgroundColor:
                                    "rgba(56, 189, 248, 0.18)",

                                pointBackgroundColor:
                                    "rgba(52, 211, 153, 1)",

                                pointBorderColor:
                                    "rgba(255, 255, 255, 0.9)"
                            }
                        ]
                    },

                    options: {
                        responsive: true,

                        maintainAspectRatio: true,

                        animation: {
                            duration: 650
                        },

                        scales: {
                            r: {
                                beginAtZero: true,

                                min: 0,

                                max: maximumScore,

                                ticks: {
                                    display: false,

                                    stepSize:
                                        Math.max(
                                            1,
                                            maximumScore / 5
                                        )
                                },

                                angleLines: {
                                    color:
                                        "rgba(148, 163, 184, 0.22)"
                                },

                                grid: {
                                    color:
                                        "rgba(148, 163, 184, 0.22)"
                                },

                                pointLabels: {
                                    color:
                                        "rgba(248, 250, 252, 0.92)",

                                    font: {
                                        size: 13,
                                        weight: "600"
                                    }
                                }
                            }
                        },

                        plugins: {
                            legend: {
                                labels: {
                                    color:
                                        "rgba(248, 250, 252, 0.92)"
                                }
                            },

                            tooltip: {
                                callbacks: {
                                    label(context) {
                                        const index =
                                            context.dataIndex;

                                        const originalScore =
                                            rawScores[index];

                                        if (
                                            originalScore === null ||
                                            originalScore === undefined
                                        ) {
                                            return (
                                                `${labels[index]}: ` +
                                                "Not evaluated"
                                            );
                                        }

                                        return (
                                            `${labels[index]}: ` +
                                            `${originalScore}/${maximumScore}`
                                        );
                                    }
                                }
                            }
                        }
                    }
                }
            );
    }

    function renderReport(report) {
        renderOverall(report);
        renderCoachStatus(report);
        renderFeedback(report);
        renderRadarChart(report);
    }

    function showPageError(message) {
        setText(
            overallScoreElement,
            "--"
        );

        overallScoreElement.dataset.status =
            "error";

        setText(
            coachStatusElement,
            "Unable to load report"
        );

        coachStatusElement.dataset.status =
            "error";

        feedbackListElement.innerHTML = "";

        feedbackListElement.appendChild(
            createFeedbackItem(
                "Report error",
                message,
                "error"
            )
        );

        radarCanvas.style.display =
            "none";
    }

    async function loadReport() {
        const assessmentId =
            getAssessmentId();

        if (!assessmentId) {
            const storedReport =
                sessionStorage.getItem(
                    "aiMotionReport"
                );

            if (storedReport) {
                try {
                    renderReport(
                        JSON.parse(storedReport)
                    );

                    return;
                } catch (error) {
                    console.error(error);
                }
            }

            showPageError(
                "The report URL does not contain an assessment ID."
            );

            return;
        }

        try {
            const response =
                await motionAPI.getReport(
                    assessmentId
                );

            if (!response.success) {
                throw new Error(
                    response?.error?.message ||
                    "Unable to retrieve the report."
                );
            }

            sessionStorage.setItem(
                "aiMotionReport",
                JSON.stringify(
                    response.data
                )
            );

            renderReport(
                response.data
            );
        } catch (error) {
            console.error(error);

            showPageError(
                error.message ||
                "An unexpected error occurred while loading the report."
            );
        }
    }

    backButton.addEventListener(
        "click",
        () => {
            window.location.href =
                "index.html";
        }
    );

    await loadReport();
});