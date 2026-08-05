// =====================================================
// AI Motion Platform
// Main Frontend Application
// =====================================================

document.addEventListener("DOMContentLoaded", () => {
    const videoInput =
        document.getElementById("videoInput");

    const analyzeButton =
        document.getElementById("analyzeButton");

    const statusText =
        document.getElementById("statusText");

    const progressFill =
        document.getElementById("progressFill");

    let selectedVideo = null;
    let isAnalyzing = false;

    function setStatus(
        message,
        status = "default"
    ) {
        statusText.textContent = message;

        if (status === "default") {
            statusText.removeAttribute(
                "data-status"
            );

            return;
        }

        statusText.dataset.status = status;
    }

    function setProgress(value) {
        const normalizedValue =
            Math.min(
                100,
                Math.max(
                    0,
                    Number(value) || 0
                )
            );

        progressFill.style.width =
            `${normalizedValue}%`;
    }

    function setAnalyzingState(analyzing) {
        isAnalyzing = analyzing;

        analyzeButton.disabled = analyzing;
        videoInput.disabled = analyzing;

        analyzeButton.textContent =
            analyzing
                ? "Analyzing..."
                : "Start Analysis";
    }

    function validateVideo(file) {
        if (!file) {
            throw new Error(
                "Please choose a video first."
            );
        }

        const allowedExtensions = [
            ".mp4",
            ".mov"
        ];

        const fileName =
            file.name.toLowerCase();

        const isAllowedExtension =
            allowedExtensions.some(
                (extension) =>
                    fileName.endsWith(extension)
            );

        if (!isAllowedExtension) {
            throw new Error(
                "Only MP4 and MOV videos are supported."
            );
        }

        const maxFileSize =
            100 * 1024 * 1024;

        if (file.size > maxFileSize) {
            throw new Error(
                "Video size must not exceed 100 MB."
            );
        }
    }

    function getStageMessage(
        stage,
        progress
    ) {
        const stageMessages = {
            uploaded:
                "Video uploaded. Waiting for analysis...",

            processing:
                "AI Motion Engine is analyzing the video...",

            motion_engine:
                "Motion Engine is detecting movement events...",

            assessment:
                "Building the movement assessment...",

            coach:
                "Coach Module is reviewing the assessment...",

            report:
                "Generating the analysis report...",

            validator:
                "Validating the analysis pipeline...",

            completed:
                "Analysis completed successfully."
        };

        if (stageMessages[stage]) {
            return stageMessages[stage];
        }

        if (progress >= 100) {
            return (
                "Analysis completed successfully."
            );
        }

        return "Analysis is in progress...";
    }

    function extractErrorMessage(
        errorResponse,
        fallbackMessage
    ) {
        return (
            errorResponse?.error?.message ||
            errorResponse?.detail ||
            fallbackMessage
        );
    }

    function delay(milliseconds) {
        return new Promise(
            (resolve) => {
                window.setTimeout(
                    resolve,
                    milliseconds
                );
            }
        );
    }

    async function waitForCompletion(
        assessmentId
    ) {
        while (true) {
            const response =
                await motionAPI
                    .getAssessmentStatus(
                        assessmentId
                    );

            if (!response.success) {
                throw new Error(
                    extractErrorMessage(
                        response,
                        "Unable to retrieve assessment status."
                    )
                );
            }

            const assessment =
                response.data;

            const progress =
                assessment.progress ?? 0;

            const stage =
                assessment.current_stage ||
                assessment.status ||
                "processing";

            setProgress(progress);

            setStatus(
                getStageMessage(
                    stage,
                    progress
                ),
                stage === "completed"
                    ? "success"
                    : "default"
            );

            if (
                assessment.status ===
                "completed"
            ) {
                return assessment;
            }

            if (
                assessment.status ===
                "failed"
            ) {
                const failureMessage =
                    assessment.failure?.message ||
                    assessment.failure?.reason ||
                    "Motion analysis failed.";

                throw new Error(
                    failureMessage
                );
            }

            await delay(
                CONFIG.POLLING_INTERVAL
            );
        }
    }

    async function startAnalysis() {
        if (isAnalyzing) {
            return;
        }

        try {
            validateVideo(
                selectedVideo
            );

            setAnalyzingState(true);

            setProgress(5);

            setStatus(
                "Uploading video..."
            );

            const createResponse =
                await motionAPI
                    .createAssessment(
                        selectedVideo
                    );

            if (!createResponse.success) {
                throw new Error(
                    extractErrorMessage(
                        createResponse,
                        "Unable to create motion assessment."
                    )
                );
            }

            const assessmentId =
                createResponse
                    .data
                    ?.assessment_id;

            if (!assessmentId) {
                throw new Error(
                    "The API did not return an assessment ID."
                );
            }

            sessionStorage.setItem(
                "aiMotionAssessmentId",
                assessmentId
            );

            setProgress(10);

            setStatus(
                `Assessment created: ${assessmentId}`
            );

            const completedAssessment =
                await waitForCompletion(
                    assessmentId
                );

            setProgress(96);

            setStatus(
                "Loading analysis report..."
            );

            const reportResponse =
                await motionAPI
                    .getReport(
                        assessmentId
                    );

            if (!reportResponse.success) {
                throw new Error(
                    extractErrorMessage(
                        reportResponse,
                        "Unable to retrieve the analysis report."
                    )
                );
            }

            sessionStorage.setItem(
                "aiMotionAssessment",
                JSON.stringify(
                    completedAssessment
                )
            );

            sessionStorage.setItem(
                "aiMotionReport",
                JSON.stringify(
                    reportResponse.data
                )
            );

            setProgress(100);

            setStatus(
                "Analysis completed. Opening report...",
                "success"
            );

            await delay(700);

            window.location.href =
                `report.html?id=${encodeURIComponent(
                    assessmentId
                )}`;
        } catch (error) {
            console.error(error);

            setProgress(0);

            setStatus(
                error.message ||
                "An unexpected error occurred.",
                "error"
            );
        } finally {
            setAnalyzingState(false);
        }
    }

    videoInput.addEventListener(
        "change",
        (event) => {
            const [file] =
                event.target.files;

            selectedVideo =
                file || null;

            setProgress(0);

            if (!selectedVideo) {
                setStatus("Waiting...");
                return;
            }

            const sizeInMB =
                selectedVideo.size /
                (1024 * 1024);

            setStatus(
                `Selected: ${selectedVideo.name} ` +
                `(${sizeInMB.toFixed(1)} MB)`
            );
        }
    );

    analyzeButton.addEventListener(
        "click",
        startAnalysis
    );

    setProgress(0);
    setStatus("Waiting...");
});